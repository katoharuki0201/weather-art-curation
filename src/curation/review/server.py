from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from ..categories import TARGETS
from ..io import atomic_json, read_json, read_jsonl
from ..models import Classified, Review

HTML = r"""<!doctype html><html lang=ja><meta charset=utf-8><title>Weather Art Review</title>
<style>body{font:15px system-ui;max-width:1200px;margin:auto;background:#f4f2ed}#card{background:white;padding:20px;margin:20px;border-radius:12px;display:grid;grid-template-columns:55% 45%;gap:18px}img{max-width:100%;max-height:70vh}button,select{font-size:16px;margin:5px;padding:8px}.tag{margin:5px}.approved{color:#08752f}.rejected{color:#b01d1d}#stats{white-space:pre-wrap}</style>
<h1>Weather Art Review</h1><p id=error role=alert></p><div><label>天気 <select id=weatherFilter onchange="applyFilter()"><option value="">すべて</option></select></label><label>時間 <select id=timeFilter onchange="applyFilter()"><option value="">すべて</option></select></label></div><p id=stats></p>
<div id=card><div><img id=image></div><div><h2 id=title></h2><strong id=status></strong><pre id=scores></pre><div id=tags></div><p><button onclick="save('approved')">A 承認</button><button onclick="save('rejected')">R 却下</button><button onclick="move(1)">S スキップ</button></p></div></div>
<script>let allItems=[],items=[],i=0,reviews={},summary={};const axes={weather:['clear','cloudy','fog','rain','snow','storm'],time:['day','twilight','night'],season:['spring','summer','autumn','winter']};
const ui={errorMessage:document.getElementById('error'),weatherSelect:document.getElementById('weatherFilter'),timeSelect:document.getElementById('timeFilter'),statsText:document.getElementById('stats'),artImage:document.getElementById('image'),artTitle:document.getElementById('title'),reviewStatus:document.getElementById('status'),scoreText:document.getElementById('scores'),tagControls:document.getElementById('tags')};
async function getJSON(url,options){const response=await fetch(url,options);if(!response.ok)throw new Error(`${url}: HTTP ${response.status} ${await response.text()}`);return response.json()}
function showError(error){ui.errorMessage.textContent=`エラー: ${error instanceof Error?error.message:String(error)}`;ui.errorMessage.style.color='#b01d1d'}
async function init(){try{[allItems,reviews,summary]=await Promise.all([getJSON('/api/items'),getJSON('/api/reviews'),getJSON('/api/stats')]);for(const value of axes.weather)ui.weatherSelect.add(new Option(value,value));for(const value of axes.time)ui.timeSelect.add(new Option(value,value));showStats();applyFilter()}catch(error){showError(error);ui.artTitle.textContent='レビュー画面を初期化できませんでした'}}
function effectiveTags(x){const r=reviews[x.id];return r&&r.tags?r.tags:x.tags}
function showStats(){ui.statsText.textContent=Object.entries(summary.counts).map(([w,ts])=>w+': '+Object.entries(ts).map(([t,n])=>`${t} ${n}/${summary.targets[w][t]}`).join(', ')).join('\n')}
function applyFilter(){const weather=ui.weatherSelect.value,time=ui.timeSelect.value;items=allItems.filter(item=>{const itemTags=effectiveTags(item);return(!weather||itemTags.weather.includes(weather))&&(!time||itemTags.time.includes(time))});i=0;render()}
function render(){if(!items.length){ui.artTitle.textContent='対象なし';ui.artImage.removeAttribute('src');ui.tagControls.innerHTML='';return}
const item=items[i],savedReview=reviews[item.id],shownTags=effectiveTags(item);ui.artImage.src=item.image.thumbUrl||item.image.url;ui.artTitle.textContent=`${i+1}/${items.length} ${item.title} — ${item.artist} (${Math.round(item.confidence*100)}%)`;ui.reviewStatus.textContent=savedReview?`保存済み: ${savedReview.status}`:'未判定';ui.reviewStatus.className=savedReview?savedReview.status:'';ui.scoreText.textContent=JSON.stringify(item.scores,null,2);ui.tagControls.innerHTML='';
for(const [axis,values] of Object.entries(axes)){ui.tagControls.innerHTML+=`<h3>${axis}</h3>`+values.map(value=>`<label class=tag><input type=checkbox data-axis=${axis} value=${value} ${shownTags[axis].includes(value)?'checked':''}>${value}</label>`).join('')}}
function move(step){if(!items.length)return;i=(i+step+items.length)%items.length;render()}
async function save(decision){if(!items.length)return;try{const item=items[i],selected={weather:[],time:[],season:[]};ui.tagControls.querySelectorAll('input:checked').forEach(input=>selected[input.dataset.axis].push(input.value));const payload={status:decision,tags:decision==='approved'?selected:null,updated_at:new Date().toISOString()};
await getJSON('/api/reviews/'+item.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});reviews[item.id]=payload;summary=await getJSON('/api/stats');ui.errorMessage.textContent='';showStats();move(1)}catch(error){showError(error)}}
document.onkeydown=e=>{if(['INPUT','SELECT'].includes(e.target.tagName))return;if(e.key==='a')save('approved');if(e.key==='r')save('rejected');if(e.key==='s')move(1)};init();</script></html>"""


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
