from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ..categories import TARGETS
from ..io import atomic_json, read_json, read_jsonl
from ..models import Classified, Review

HTML = """<!doctype html><html lang=ja><meta charset=utf-8><title>Weather Art Review</title>
<style>body{font:15px system-ui;max-width:1200px;margin:auto;background:#f4f2ed}#card{background:white;padding:20px;margin:20px;border-radius:12px;display:grid;grid-template-columns:55% 45%;gap:18px}img{max-width:100%;max-height:70vh}button,select{font-size:16px;margin:5px;padding:8px}.tag{margin:5px}.approved{color:#08752f}.rejected{color:#b01d1d}#stats{white-space:pre-wrap}</style>
<h1>Weather Art Review</h1><div><label>天気 <select id=weatherFilter onchange="applyFilter()"><option value="">すべて</option></select></label><label>時間 <select id=timeFilter onchange="applyFilter()"><option value="">すべて</option></select></label></div><p id=stats></p>
<div id=card><div><img id=image></div><div><h2 id=title></h2><strong id=status></strong><pre id=scores></pre><div id=tags></div><p><button onclick="save('approved')">A 承認</button><button onclick="save('rejected')">R 却下</button><button onclick="move(1)">S スキップ</button></p></div></div>
<script>let allItems=[],items=[],i=0,reviews={},summary={};const axes={weather:['clear','cloudy','fog','rain','snow','storm'],time:['day','twilight','night'],season:['spring','summer','autumn','winter']};
async function init(){[allItems,reviews,summary]=await Promise.all([fetch('/api/items').then(r=>r.json()),fetch('/api/reviews').then(r=>r.json()),fetch('/api/stats').then(r=>r.json())]);for(const v of axes.weather)weatherFilter.add(new Option(v,v));for(const v of axes.time)timeFilter.add(new Option(v,v));showStats();applyFilter()}
function effectiveTags(x){const r=reviews[x.id];return r&&r.tags?r.tags:x.tags}
function showStats(){stats.textContent=Object.entries(summary.counts).map(([w,ts])=>w+': '+Object.entries(ts).map(([t,n])=>`${t} ${n}/${summary.targets[w][t]}`).join(', ')).join('\n')}
function applyFilter(){const w=weatherFilter.value,t=timeFilter.value;items=allItems.filter(x=>{const tags=effectiveTags(x);return(!w||tags.weather.includes(w))&&(!t||tags.time.includes(t))});i=0;render()}
function render(){if(!items.length){title.textContent='対象なし';image.removeAttribute('src');tags.innerHTML='';return}let x=items[i],r=reviews[x.id],shown=effectiveTags(x);image.src=x.image.thumbUrl||x.image.url;title.textContent=`${i+1}/${items.length} ${x.title} — ${x.artist} (${Math.round(x.confidence*100)}%)`;status.textContent=r?`保存済み: ${r.status}`:'未判定';status.className=r?r.status:'';scores.textContent=JSON.stringify(x.scores,null,2);tags.innerHTML='';
for(const [a,vs] of Object.entries(axes)){tags.innerHTML+=`<h3>${a}</h3>`+vs.map(v=>`<label class=tag><input type=checkbox data-axis=${a} value=${v} ${shown[a].includes(v)?'checked':''}>${v}</label>`).join('')}}
function move(n){i=(i+n+items.length)%items.length;render()}async function save(state){let x=items[i],selected={weather:[],time:[],season:[]};document.querySelectorAll('input:checked').forEach(e=>selected[e.dataset.axis].push(e.value));let payload={status:state,tags:state==='approved'?selected:null,updated_at:new Date().toISOString()},r=await fetch('/api/reviews/'+x.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});if(!r.ok){alert(await r.text());return}reviews[x.id]=payload;summary=await fetch('/api/stats').then(v=>v.json());showStats();move(1)}
document.onkeydown=e=>{if(['INPUT','SELECT'].includes(e.target.tagName))return;if(e.key==='a')save('approved');if(e.key==='r')save('rejected');if(e.key==='s')move(1)};init();</script></html>"""


def create_app(classified_path: Path = Path("data/classified.jsonl"), reviews_path: Path = Path("data/reviews.json")) -> FastAPI:
    app = FastAPI(title="Weather Art Review")

    @app.get("/", response_class=HTMLResponse)
    def index(): return HTML

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
        items_by_id = {x.id: x for x in read_jsonl(classified_path, Classified)}
        counts = {w: {t: 0 for t in times} for w, times in TARGETS.items()}
        for item_id, raw in read_json(reviews_path, {}).items():
            review = Review.model_validate(raw)
            if review.status != "approved" or item_id not in items_by_id: continue
            tags = review.tags or items_by_id[item_id].tags
            for weather in tags.weather:
                for time in tags.time: counts[weather][time] += 1
        return {"counts": counts, "targets": TARGETS}
    return app
