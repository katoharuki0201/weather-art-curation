import json
from pathlib import Path
from typing import Annotated

import typer

from .categories import TARGETS
from .classify.clip import OpenClipClassifier
from .classify.service import classify_one
from .collect import COLLECTORS
from .evaluate import evaluate as evaluate_results
from .export import export_artworks
from .images import fetch_images as fetch_all_images
from .images import image_path
from .io import append_jsonl, read_json, read_jsonl
from .models import Candidate, Classified, Tags
from .review import create_app

app = typer.Typer(no_args_is_help=True)
DATA = Path("data")


@app.command()
def collect(source: Annotated[str, typer.Option(help="aic, met, or cma")], limit: int = 200, include_works_on_paper: bool = False, aic_contact: str | None = typer.Option(None, envvar="CURATION_AIC_CONTACT", help="AIC User-Agent contact email or project URL"), query: Annotated[list[str] | None, typer.Option("--query", help="Search terms; repeat or comma-separate")] = None):
    if source not in COLLECTORS: raise typer.BadParameter("source must be aic, met, or cma")
    path = DATA / "candidates.jsonl"
    existing = {x.id for x in read_jsonl(path, Candidate)}
    try:
        queries = [value.strip() for group in (query or []) for value in group.split(",") if value.strip()] or None
        result = COLLECTORS[source](limit, include_works_on_paper, existing, aic_contact, queries)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--aic-contact") from exc
    append_jsonl(path, result.items)
    detail_failures = ",".join(f"{key}:{value}" for key, value in sorted(result.detail_failures.items())) or "none"
    typer.echo(f"queries={','.join(result.queries)} added={len(result.items)} scanned={result.scanned} skipped_existing={result.skipped_existing} duplicates={result.duplicates} rejected={result.rejected} failed_detail={result.failed_detail} detail_reasons={detail_failures}")


@app.command("fetch-images")
def fetch_images(cache: Path = DATA / "cache/images", interval: float = 1.0, aic_contact: str | None = typer.Option(None, envvar="CURATION_AIC_CONTACT", help="AIC image request contact email or project URL"), source: Annotated[list[str] | None, typer.Option("--source", help="Sources to fetch; repeat or comma-separate: aic,met,cma")] = None):
    selected = {value.strip() for group in (source or []) for value in group.split(",") if value.strip()}
    invalid = selected - set(COLLECTORS)
    if invalid:
        raise typer.BadParameter(f"unknown source(s): {', '.join(sorted(invalid))}", param_hint="--source")
    candidates = read_jsonl(DATA / "candidates.jsonl", Candidate)
    if selected:
        candidates = [item for item in candidates if item.source in selected]
    try:
        result = fetch_all_images(candidates, cache, interval, aic_contact)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--aic-contact") from exc
    for failure in result.failures:
        typer.echo(f"failed {failure.id}: {failure.reason}", err=True)
    if any(failure.code == "aic_cloudflare_challenge" for failure in result.failures):
        typer.echo("AIC IIIFの既知Cloudflare障害です。Met/CMAを利用してください。", err=True)
    typer.echo(f"fetched={result.fetched} skipped={result.skipped} failed={result.failed}")


@app.command()
def classify(cache: Path = DATA / "cache/images", threshold: float = 0.25, model: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k", source: Annotated[list[str] | None, typer.Option("--source", help="Sources; repeat or comma-separate")] = None):
    output = DATA / "classified.jsonl"
    selected = {value.strip() for group in (source or []) for value in group.split(",") if value.strip()}
    invalid = selected - set(COLLECTORS)
    if invalid: raise typer.BadParameter(f"unknown source(s): {', '.join(sorted(invalid))}", param_hint="--source")
    candidates = read_jsonl(DATA / "candidates.jsonl", Candidate)
    if selected: candidates = [item for item in candidates if item.source in selected]
    done = {x.id for x in read_jsonl(output, Classified)}
    classifier = None
    added = 0
    skipped_done = 0
    missing = {name: 0 for name in COLLECTORS}
    for item in candidates:
        if item.id in done:
            skipped_done += 1
            continue
        path = image_path(cache, item)
        if not path.exists():
            missing[item.source] += 1
            continue
        if classifier is None:
            classifier = OpenClipClassifier(model, pretrained)
        append_jsonl(output, [classify_one(item, path, classifier, threshold)]); added += 1
    missing_text = ",".join(f"{key}={value}" for key, value in missing.items() if value)
    typer.echo(f"classified={added} skipped_existing={skipped_done} missing_images={missing_text or 'none'}")


@app.command()
def evaluate(labeled: Path = Path("eval/labeled.jsonl")):
    labels = {}
    if labeled.exists():
        for line in labeled.read_text(encoding="utf-8").splitlines():
            if line.strip():
                raw = json.loads(line); labels[raw["id"]] = Tags.model_validate(raw["tags"])
    typer.echo(json.dumps(evaluate_results(read_jsonl(DATA / "classified.jsonl", Classified), labels), ensure_ascii=False, indent=2))


@app.command()
def review(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run(create_app(), host=host, port=port)


@app.command("export")
def export_command(output: Path = Path("dist/artworks.json"), schema: Path = Path("schema/artwork.schema.json")):
    values = export_artworks(read_jsonl(DATA / "classified.jsonl", Classified), DATA / "reviews.json", schema, output)
    typer.echo(f"exported={len(values)} to {output}")


@app.command()
def stats():
    values = [item for item in read_jsonl(DATA / "classified.jsonl", Classified) if item.sky_visible]
    reviews = read_json(DATA / "reviews.json", {})
    counts = {w: {t: 0 for t in times} for w, times in TARGETS.items()}
    progress = {"approved": 0, "rejected": 0, "skipped": 0, "unreviewed": len(values)}
    sources = {name: 0 for name in COLLECTORS}
    for item in values: sources[item.source] += 1
    for item in values:
        raw = reviews.get(item.id)
        if not raw: continue
        state = raw.get("status")
        if state in progress:
            progress[state] += 1
            progress["unreviewed"] -= 1
        if state != "approved": continue
        tags = Tags.model_validate(raw.get("tags") or item.tags.model_dump())
        for w in tags.weather:
            for t in tags.time: counts[w][t] += 1
    typer.echo("progress: " + ", ".join(f"{key}={value}" for key, value in progress.items()))
    typer.echo("sources: " + ", ".join(f"{key}={value}" for key, value in sources.items()))
    for weather, times in counts.items():
        typer.echo(weather + ": " + ", ".join(f"{time}={count}/{TARGETS[weather][time]} missing={max(0, TARGETS[weather][time]-count)}" for time, count in times.items()))


if __name__ == "__main__": app()
