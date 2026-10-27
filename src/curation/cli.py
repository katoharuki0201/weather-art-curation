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
def collect(source: Annotated[str, typer.Option(help="aic, met, or cma")], limit: int = 200, include_works_on_paper: bool = False, aic_contact: str | None = typer.Option(None, envvar="CURATION_AIC_CONTACT", help="AIC User-Agent contact email or project URL")):
    if source not in COLLECTORS: raise typer.BadParameter("source must be aic, met, or cma")
    path = DATA / "candidates.jsonl"
    existing = {x.id for x in read_jsonl(path, Candidate)}
    try:
        result = COLLECTORS[source](limit, include_works_on_paper, existing, aic_contact)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--aic-contact") from exc
    append_jsonl(path, result.items)
    typer.echo(f"added={len(result.items)} skipped_existing={result.skipped_existing} rejected={result.rejected}")


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
def classify(cache: Path = DATA / "cache/images", threshold: float = 0.25, model: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
    output = DATA / "classified.jsonl"
    done = {x.id for x in read_jsonl(output, Classified)}
    classifier = OpenClipClassifier(model, pretrained)
    added = 0
    for item in read_jsonl(DATA / "candidates.jsonl", Candidate):
        if item.id in done: continue
        path = image_path(cache, item)
        if not path.exists():
            typer.echo(f"missing image: {item.id}", err=True); continue
        append_jsonl(output, [classify_one(item, path, classifier, threshold)]); added += 1
    typer.echo(f"classified={added} skipped={len(done)}")


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
    values = read_jsonl(DATA / "classified.jsonl", Classified)
    reviews = read_json(DATA / "reviews.json", {})
    counts = {w: {t: 0 for t in times} for w, times in TARGETS.items()}
    for item in values:
        raw = reviews.get(item.id)
        if not raw or raw.get("status") != "approved": continue
        tags = Tags.model_validate(raw.get("tags") or item.tags.model_dump())
        for w in tags.weather:
            for t in tags.time: counts[w][t] += 1
    for weather, times in counts.items():
        typer.echo(weather + ": " + ", ".join(f"{time}={count}/{TARGETS[weather][time]}" for time, count in times.items()))


if __name__ == "__main__": app()
