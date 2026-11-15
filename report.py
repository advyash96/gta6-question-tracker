"""Build a CSV and a self-contained HTML report from the collected questions."""
from __future__ import annotations

import csv
import html
import json
import re
import time
from collections import Counter
from pathlib import Path


def _norm(text: str) -> str:
    """Rough key for spotting the same question asked by different people."""
    t = re.sub(r"https?://\S+|@\w+|[^a-z0-9 ]", " ", text.lower())
    t = re.sub(r"\b(gta ?(6|vi)|grand theft auto ?(6|vi)|the|a|an|is|are|do|does|will|guys|anyone|know)\b", " ", t)
    return " ".join(t.split()[:12])


def write_csv(rows, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["platform", "topics", "question", "url", "where", "posted", "collected"])
        for r in rows:
            w.writerow([r["platform"], r["topics"], r["text"], r["url"], r["context"],
                        r["posted"], time.strftime("%Y-%m-%d %H:%M", time.localtime(r["found_at"]))])


def write_html(rows, path: Path, days: int | None) -> None:
    topic_counts = Counter(t for r in rows for t in r["topics"].split(";"))
    platform_counts = Counter(r["platform"] for r in rows)
    groups = Counter(_norm(r["text"]) for r in rows)
    first_text = {}
    for r in rows:
        first_text.setdefault(_norm(r["text"]), r["text"])
    repeated = [(n, first_text[k]) for k, n in groups.most_common(15) if n > 1 and k]

    data = [{"p": r["platform"], "t": r["topics"], "q": r["text"][:500], "u": r["url"]} for r in rows]
    max_topic = max(topic_counts.values(), default=1)
    bars = "".join(
        f'<div class="bar"><span class="lbl">{html.escape(t)}</span>'
        f'<span class="track"><span class="fill" style="width:{100 * n / max_topic:.1f}%"></span></span>'
        f'<span class="num">{n}</span></div>'
        for t, n in topic_counts.most_common()
    )
    rep = "".join(f"<li><b>{n}×</b> {html.escape(q[:200])}</li>" for n, q in repeated) or "<li>None yet</li>"
    scope = f"last {days} days" if days else "all time"
    plat = " · ".join(f"{p.capitalize()}: {n}" for p, n in platform_counts.most_common())

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>GTA 6 Questions</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--accent:#c2410c;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--fg:#ecebe6;--muted:#9a9993;--line:#2c2c2a;--accent:#fb923c;--card:#1d1d1c}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:24px 16px}}
h1{{margin:0 0 4px;font-size:26px}} h2{{font-size:17px;margin:28px 0 10px}}
.muted{{color:var(--muted)}} .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}}
.bar{{display:grid;grid-template-columns:190px 1fr 44px;gap:10px;align-items:center;margin:6px 0}}
.track{{background:var(--line);border-radius:4px;height:12px;overflow:hidden}} .fill{{display:block;height:100%;background:var(--accent)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
@media (max-width:600px){{.bar{{grid-template-columns:110px 1fr 36px;font-size:13px}}}}
input,select{{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}} input{{flex:1;min-width:180px}}
.q{{border-top:1px solid var(--line);padding:10px 0}} .q a{{color:var(--accent)}}
.tag{{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:99px;padding:0 8px;margin:0 4px 0 0;color:var(--muted)}}
ol{{padding-left:20px}} li{{margin:4px 0}}
</style></head><body><main>
<h1>What people are asking about GTA 6</h1>
<div class="muted">{len(rows)} questions · {scope} · {html.escape(plat)} · generated {time.strftime("%Y-%m-%d %H:%M")}</div>
<h2>Questions by topic</h2><div class="card">{bars or "No data yet"}</div>
<h2>Most repeated questions</h2><div class="card"><ol>{rep}</ol></div>
<h2>All questions</h2>
<div class="filters"><input id="s" placeholder="Search questions..."><select id="tp"><option value="">All topics</option>
{"".join(f'<option>{html.escape(t)}</option>' for t, _ in topic_counts.most_common())}</select>
<select id="pf"><option value="">All platforms</option>{"".join(f'<option value="{p}">{p.capitalize()}</option>' for p in platform_counts)}</select></div>
<div class="muted" id="cnt"></div><div id="list"></div>
</main><script>
const D={json.dumps(data).replace("</", "<\\/")};
const esc=s=>s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
function draw(){{const s=document.getElementById('s').value.toLowerCase(),t=document.getElementById('tp').value,p=document.getElementById('pf').value;
const r=D.filter(d=>(!s||d.q.toLowerCase().includes(s))&&(!t||d.t.split(';').includes(t))&&(!p||d.p===p));
document.getElementById('cnt').textContent=r.length+' shown';
document.getElementById('list').innerHTML=r.slice(0,500).map(d=>`<div class="q"><div>${{esc(d.q)}}</div><div class="muted">${{d.t.split(';').map(x=>`<span class="tag">${{esc(x)}}</span>`).join('')}} ${{esc(d.p)}} · <a href="${{esc(d.u)}}" target="_blank" rel="noopener">open</a></div></div>`).join('');}}
['s','tp','pf'].forEach(id=>document.getElementById(id).addEventListener('input',draw));draw();
</script></body></html>"""
    path.write_text(page, encoding="utf-8")
