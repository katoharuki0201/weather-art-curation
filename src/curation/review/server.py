from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from ..categories import TIMES, WEATHER
from ..io import atomic_json, read_json, read_jsonl
from ..models import Classified, Review

HTML = r"""<!doctype html><html lang=ja><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>作品レビュー</title>
<style>
:root{color-scheme:light;--black:#111;--mid:#777;--line:#d8d8d8;--soft:#f3f3f3;--white:#fff}*{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--black);font:15px/1.55 system-ui,-apple-system,sans-serif}.shell{max-width:1280px;margin:auto;padding:24px}
.top{display:flex;justify-content:space-between;align-items:end;gap:24px;margin-bottom:18px}h1{font-size:24px;margin:0}.sources{color:var(--mid)}.progress{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:16px 0}.metric{background:var(--white);border:1px solid var(--line);border-radius:10px;padding:12px}.metric b{display:block;font-size:24px}
.bar{height:7px;background:#ddd;border-radius:9px;overflow:hidden;margin-top:12px}.bar span{display:block;height:100%;background:var(--black)}.workspace{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(340px,.7fr);background:var(--white);border:1px solid var(--line);border-radius:14px;overflow:hidden}.visual{display:grid;place-items:center;background:#e8e8e8;min-height:620px;padding:20px}
.visual img{max-width:100%;max-height:75vh;object-fit:contain}.panel{padding:26px;border-left:1px solid var(--line)}.eyebrow{display:flex;justify-content:space-between;color:var(--mid);font-size:13px}.panel h2{font-size:24px;line-height:1.25;margin:10px 0 4px}.artist{color:var(--mid);margin:0 0 18px}.saved{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.axis{margin:22px 0 0}.axis h3{font-size:13px;margin:0 0 8px;color:var(--mid)}.chips{display:flex;flex-wrap:wrap;gap:8px}.chip input{position:absolute;opacity:0;pointer-events:none}.chip span{display:block;padding:9px 13px;border:1px solid var(--line);border-radius:8px;background:var(--white);cursor:pointer;font-weight:600}.chip input:checked+span{color:var(--white);background:var(--black);border-color:var(--black)}
details{margin:22px 0;color:var(--mid)}pre{overflow:auto;font-size:12px}.actions{display:grid;grid-template-columns:2fr 1fr 1fr;gap:8px;margin-top:24px}.actions button,.nav button{border:1px solid var(--black);border-radius:8px;padding:12px;background:var(--white);font-weight:700;cursor:pointer}.actions .primary{background:var(--black);color:var(--white)}.nav{display:flex;justify-content:space-between;margin-top:10px}.nav button{border-color:var(--line)}
#error{background:var(--black);color:var(--white);padding:10px;border-radius:8px}.empty{color:var(--mid)}@media(max-width:850px){.shell{padding:14px}.top{display:block}.progress{grid-template-columns:repeat(2,1fr)}.workspace{grid-template-columns:1fr}.visual{min-height:360px}.panel{border-left:0;border-top:1px solid var(--line);padding:20px}.actions{grid-template-columns:1fr}.sources{margin-top:8px}}
</style>
<main class=shell><header class=top><div><h1>作品レビュー</h1><div id=position class=empty>読み込み中…</div></div><div id=sources class=sources></div></header><p id=error role=alert hidden></p><section><div id=progress class=progress></div><div class=bar><span id=progressBar></span></div></section>
<section class=workspace><div class=visual><img id=image alt="レビュー対象作品"></div><article class=panel><div class=eyebrow><span id=confidence></span><span id=status class=saved></span></div><h2 id=title></h2><p id=artist class=artist></p><div id=tags></div><details><summary>分類スコアを表示</summary><pre id=scores></pre></details>
<div class=actions><button class=primary onclick="save('approved')">承認 A</button><button onclick="save('rejected')">却下 R</button><button onclick="save('skipped')">スキップ S</button></div><div class=nav><button onclick="move(-1)">← 前へ</button><button onclick="move(1)">次へ →</button></div></article></section></main>
<script>let items=[],i=0,reviews={},summary={};const axes={weather:{label:'天気',values:{clear:'晴れ',cloudy:'曇り',fog:'霧',rain:'雨',snow:'雪',storm:'嵐'}},time:{label:'時間帯',values:{day:'昼',twilight:'朝夕',night:'夜'}},season:{label:'季節',values:{spring:'春',summer:'夏',autumn:'秋',winter:'冬'}}},statusLabels={approved:'承認',rejected:'却下',skipped:'スキップ',unreviewed:'未判定'};
const ui={error:document.getElementById('error'),position:document.getElementById('position'),sources:document.getElementById('sources'),progress:document.getElementById('progress'),progressBar:document.getElementById('progressBar'),image:document.getElementById('image'),confidence:document.getElementById('confidence'),status:document.getElementById('status'),title:document.getElementById('title'),artist:document.getElementById('artist'),tags:document.getElementById('tags'),scores:document.getElementById('scores')};
async function getJSON(url,options){const response=await fetch(url,options);if(!response.ok)throw new Error(`${url}: HTTP ${response.status} ${await response.text()}`);return response.json()}
function showError(error){ui.error.hidden=false;ui.error.textContent=`エラー: ${error instanceof Error?error.message:String(error)}`}
async function init(){try{[items,reviews,summary]=await Promise.all([getJSON('/api/items'),getJSON('/api/reviews'),getJSON('/api/stats')]);showStats();render()}catch(error){showError(error);ui.position.textContent='レビュー画面を初期化できませんでした'}}
function effectiveTags(item){const review=reviews[item.id];return review&&review.tags?review.tags:item.tags}
function showStats(){const total=Object.values(summary.progress).reduce((sum,value)=>sum+value,0),done=total-summary.progress.unreviewed;ui.progress.innerHTML=Object.entries(summary.progress).map(([key,value])=>`<div class=metric><span>${statusLabels[key]}</span><b>${value}</b></div>`).join('');ui.progressBar.style.width=`${total?done/total*100:0}%`;ui.sources.textContent='収集元 '+Object.entries(summary.sources).map(([key,value])=>`${key.toUpperCase()} ${value}`).join(' · ')}
function render(){if(!items.length){ui.position.textContent='対象作品はありません';ui.image.removeAttribute('src');ui.tags.innerHTML='';return}const item=items[i],review=reviews[item.id],shown=effectiveTags(item);ui.position.textContent=`${i+1} / ${items.length}`;ui.image.src=item.image.url;ui.title.textContent=item.title;ui.artist.textContent=`${item.artist}${item.date?' · '+item.date:''}`;ui.confidence.textContent=`確信度 ${Math.round(item.confidence*100)}%`;ui.status.textContent=statusLabels[review?.status||'unreviewed'];ui.scores.textContent=JSON.stringify(item.scores,null,2);
ui.tags.innerHTML=Object.entries(axes).map(([axis,definition])=>`<section class=axis><h3>${definition.label}</h3><div class=chips>${Object.entries(definition.values).map(([value,label])=>`<label class=chip><input type=checkbox data-axis=${axis} value=${value} ${shown[axis].includes(value)?'checked':''}><span>${label}</span></label>`).join('')}</div></section>`).join('')}
function move(step){if(!items.length)return;i=(i+step+items.length)%items.length;render()}
async function save(decision){if(!items.length)return;try{const item=items[i],selected={weather:[],time:[],season:[]};ui.tags.querySelectorAll('input:checked').forEach(input=>selected[input.dataset.axis].push(input.value));const payload={status:decision,tags:decision==='approved'?selected:null,updated_at:new Date().toISOString()};await getJSON('/api/reviews/'+item.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});reviews[item.id]=payload;summary=await getJSON('/api/stats');ui.error.hidden=true;showStats();move(1)}catch(error){showError(error)}}
document.onkeydown=event=>{if(event.target.tagName==='INPUT')return;if(event.key==='a')save('approved');if(event.key==='r')save('rejected');if(event.key==='s')save('skipped');if(event.key==='ArrowLeft')move(-1);if(event.key==='ArrowRight')move(1)};init();</script></html>"""


def create_app(classified_path: Path = Path("data/classified.jsonl"), reviews_path: Path = Path("data/reviews.json")) -> FastAPI:
    app = FastAPI(title="Weather Art Review")

    @app.get("/", response_class=HTMLResponse)
    def index(): return HTML

    @app.get("/favicon.ico", response_class=Response, status_code=204)
    def favicon(): return Response(status_code=204)

    @app.get("/api/items")
    def items():
        values = [x for x in read_jsonl(classified_path, Classified) if x.sky_visible]
        return sorted(values, key=lambda x: x.confidence, reverse=True)

    @app.get("/api/reviews")
    def reviews(): return read_json(reviews_path, {})

    @app.put("/api/reviews/{item_id}")
    def save(item_id: str, review: Review):
        known = {x.id for x in read_jsonl(classified_path, Classified)}
        if item_id not in known: raise HTTPException(404, "unknown artwork")
        data = read_json(reviews_path, {})
        data[item_id] = review.model_dump(mode="json")
        atomic_json(reviews_path, data)
        return {"ok": True}

    @app.get("/api/stats")
    def stats():
        items_by_id = {x.id: x for x in read_jsonl(classified_path, Classified) if x.sky_visible}
        counts = {weather: {time: 0 for time in TIMES} for weather in WEATHER}
        progress = {"approved": 0, "rejected": 0, "skipped": 0, "unreviewed": len(items_by_id)}
        sources = {"aic": 0, "met": 0, "cma": 0}
        for item in items_by_id.values(): sources[item.source] += 1
        for item_id, raw in read_json(reviews_path, {}).items():
            review = Review.model_validate(raw)
            if item_id not in items_by_id: continue
            progress[review.status] += 1
            progress["unreviewed"] -= 1
            if review.status != "approved": continue
            tags = review.tags or items_by_id[item_id].tags
            for weather in tags.weather:
                for time in tags.time: counts[weather][time] += 1
        return {"counts": counts, "progress": progress, "sources": sources}
    return app
