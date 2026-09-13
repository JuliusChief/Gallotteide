"""Albero Genealogico Gallotta – interactive HTML family tree."""

import json, webbrowser
import pandas as pd
from collections import defaultdict
from pathlib import Path

INPUT_FILE = "Albero_Genealogico_Gallotta.xlsx"
HTML_FILE  = "albero_gallotta.html"
AUTO_OPEN  = True

# ── Layout constants (also embedded in JS) ───────────────────────────────────
BOX_W      = 130   # px – person box width
BOX_H      = 44    # px – person box height
SPOUSE_GAP = 30    # px – marriage-line gap between spouse box edges
FAMILY_PAD = 65    # px – minimum gap between adjacent family groups
V_GAP      = 130   # px – vertical distance between generation centres
CONN_DROP  = 16    # px – length of vertical stub below parent before horizontal bar

H_UNIT = BOX_W + SPOUSE_GAP   # 160 px  (centre-to-centre for a couple)

GEN_META = {
    1: {"fill": "#f9d0cc", "stroke": "#c0392b", "label": "Generazione 1"},
    2: {"fill": "#cce3f5", "stroke": "#2471a3", "label": "Generazione 2"},
    3: {"fill": "#cdf0d8", "stroke": "#1e8449", "label": "Generazione 3"},
    4: {"fill": "#e4d4f4", "stroke": "#7d3c98", "label": "Generazione 4"},
    5: {"fill": "#fdf0cc", "stroke": "#d68910", "label": "Generazione 5"},
}

# ── 1. LOAD DATA ─────────────────────────────────────────────────────────────
df_p = pd.read_excel(INPUT_FILE, sheet_name="Persone")
df_r = pd.read_excel(INPUT_FILE, sheet_name="Relazioni")

persons = {}
for _, r in df_p.iterrows():
    label = f"{r.nome} {r.cognome}"
    nick  = str(r.soprannome).strip() if pd.notna(r.soprannome) and str(r.soprannome).strip() else ""
    persons[int(r.person_id)] = {
        "label": label, "nick": nick,
        "nome": str(r.nome), "cognome": str(r.cognome),
        "gen": int(r.generazione),
    }

person_spouses = defaultdict(list)
seen_marriages = set()
all_marriages  = []
parents_of     = defaultdict(list)
children_of    = defaultdict(list)

for _, r in df_r[df_r.tipo == "matrimonio"].iterrows():
    p1, p2 = int(r.person_id_1), int(r.person_id_2)
    key = (min(p1, p2), max(p1, p2))
    if key not in seen_marriages:
        seen_marriages.add(key)
        all_marriages.append(key)
        person_spouses[p1].append(p2)
        person_spouses[p2].append(p1)

for _, r in df_r[df_r.tipo == "genitore"].iterrows():
    parent, child = int(r.person_id_1), int(r.person_id_2)
    parents_of[child].append(parent)
    children_of[parent].append(child)

couple_children = {
    m: sorted(set(children_of[m[0]]) & set(children_of[m[1]]))
    for m in all_marriages
}

# ── 2. FIX MISSING GEN-2 GALLOTTA CONNECTIONS ────────────────────────────────
# Five gen-2 Gallotta children have no parent rows → link them to (1, 2).
GEN1 = (1, 2)
for pid, info in persons.items():
    if info["gen"] == 2 and info["cognome"] == "Gallotta" and not parents_of.get(pid):
        parents_of[pid] = [1, 2]
        for gp in (1, 2):
            if pid not in children_of[gp]:
                children_of[gp].append(pid)
        cc = couple_children.setdefault(GEN1, [])
        if pid not in cc:
            cc.append(pid)
            cc.sort()

# ── 3. TREE STRUCTURE ─────────────────────────────────────────────────────────
primary_couple = {
    pid: tuple(sorted([pid, sp_list[0]]))
    for pid, sp_list in person_spouses.items()
}

def tree_children(ck):
    raw = couple_children.get(ck, []) if len(ck) == 2 else [
        c for c in children_of[ck[0]] if len(parents_of[c]) == 1
    ]
    seen_ck, result = set(), []
    for k in sorted(raw):
        child_ck = primary_couple.get(k, (k,))
        if child_ck not in seen_ck:
            seen_ck.add(child_ck)
            result.append(child_ck)
    return result

all_ck = set(all_marriages)
for pid in persons:
    if not person_spouses[pid]:
        ck_s = (pid,)
        if tree_children(ck_s):
            all_ck.add(ck_s)

root_cks = sorted(
    [ck for ck in all_ck if all(not parents_of.get(p) for p in ck)],
    key=lambda ck: ck[0],
)

# ── 4. SUBTREE WIDTHS ─────────────────────────────────────────────────────────
_w = {}

def subtree_width(ck):
    if ck in _w:
        return _w[ck]
    kids = tree_children(ck)
    min_w = len(ck) * H_UNIT + FAMILY_PAD
    sec_extra = sum(
        (len(couple_children.get(tuple(sorted([p, sp])), [])) + 1) * H_UNIT + FAMILY_PAD
        for p in ck for sp in person_spouses[p][1:]
    )
    w = (max(sum(subtree_width(c) for c in kids), min_w) if kids else min_w) + sec_extra
    _w[ck] = w
    return w

# ── 5. ASSIGN POSITIONS ───────────────────────────────────────────────────────
pos = {}

def place(ck, cx):
    cy = (persons[ck[0]]["gen"] - 1) * V_GAP
    if len(ck) == 2:
        pos[ck[0]] = (cx - H_UNIT / 2, cy)
        pos[ck[1]] = (cx + H_UNIT / 2, cy)
    else:
        pos[ck[0]] = (cx, cy)
    kids = tree_children(ck)
    if not kids:
        return
    sec_extra = sum(
        (len(couple_children.get(tuple(sorted([p, sp])), [])) + 1) * H_UNIT + FAMILY_PAD
        for p in ck for sp in person_spouses[p][1:]
    )
    total = sum(subtree_width(c) for c in kids)
    x = cx - (total + sec_extra) / 2
    for c in kids:
        w = subtree_width(c)
        own_sec = sum(
            (len(couple_children.get(tuple(sorted([p2, sp])), [])) + 1) * H_UNIT + FAMILY_PAD
            for p2 in c for sp in person_spouses[p2][1:]
        )
        place(c, x + (w - own_sec) / 2)
        x += w

x_off = 0
for rck in root_cks:
    w = subtree_width(rck)
    place(rck, x_off + w / 2)
    x_off += w + FAMILY_PAD * 2

# Secondary spouses: place immediately right of primary spouse (not at row end)
for pid, sp_list in person_spouses.items():
    if len(sp_list) < 2 or pid not in pos:
        continue
    pid_cy = (persons[pid]["gen"] - 1) * V_GAP
    prim_sp = sp_list[0]
    anchor_x = pos[prim_sp][0] if prim_sp in pos else pos[pid][0]
    for sec_sp in sp_list[1:]:
        if sec_sp in pos:
            continue
        sec_x = anchor_x + H_UNIT + FAMILY_PAD
        pos[sec_sp] = (sec_x, pid_cy)
        sec_key = tuple(sorted([pid, sec_sp]))
        sec_kids = couple_children.get(sec_key, [])
        mid_x = (pos[pid][0] + sec_x) / 2
        for i, kid in enumerate(sec_kids):
            if kid not in pos:
                kid_cy = (persons[kid]["gen"] - 1) * V_GAP
                pos[kid] = (mid_x + (i - (len(sec_kids) - 1) / 2) * H_UNIT, kid_cy)

# ── 6. BUILD JSON FOR JAVASCRIPT ──────────────────────────────────────────────
persons_js = {
    str(pid): {
        "label": info["label"], "nick": info["nick"],
        "gen":   info["gen"],
        "x":     round(pos[pid][0], 1),
        "y":     round(pos[pid][1], 1),
    }
    for pid, info in persons.items() if pid in pos
}

couples_js = []
for m in all_marriages:
    p1, p2 = m
    if p1 not in pos or p2 not in pos:
        continue
    secondary = len(person_spouses[p1]) > 1 and person_spouses[p1][0] != p2
    couples_js.append({
        "id": f"m{p1}_{p2}", "p1": p1, "p2": p2,
        "children": [k for k in couple_children.get(m, []) if k in pos],
        "secondary": secondary,
    })

gens_present = sorted({info["gen"] for info in persons.values()})
legend_html = "".join(
    f'<div class="li"><span class="ld" style="background:{GEN_META[g]["fill"]};'
    f'border:2px solid {GEN_META[g]["stroke"]}"></span>{GEN_META[g]["label"]}</div>'
    for g in gens_present
) + (
    '<div class="li" style="margin-top:7px;border-top:1px solid #eee;padding-top:5px">'
    '<svg width="26" height="10"><line x1="0" y1="5" x2="26" y2="5" '
    'stroke="#e74c3c" stroke-width="2" stroke-dasharray="5,3"/></svg>'
    ' Secondo matrimonio</div>'
)

# ── 7. GENERATE HTML ──────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Albero Genealogico Gallotta</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f0ede8;font-family:Georgia,serif;overflow:hidden;touch-action:none}}
#title{{position:fixed;top:12px;left:50%;transform:translateX(-50%);font-size:22px;
  color:#2c2c2c;letter-spacing:.5px;text-shadow:1px 1px 3px rgba(255,255,255,.8);
  z-index:20;pointer-events:none}}
#legend{{position:fixed;top:52px;left:14px;background:rgba(255,255,255,.93);
  border:1px solid #ccc;border-radius:10px;padding:10px 14px;font-size:12px;
  z-index:20;box-shadow:0 2px 8px rgba(0,0,0,.12)}}
#legend h4{{margin-bottom:6px;font-size:13px;color:#333;font-weight:bold}}
.li{{display:flex;align-items:center;gap:7px;margin:4px 0;color:#444}}
.ld{{width:16px;height:14px;border-radius:3px;flex-shrink:0}}
#controls{{position:fixed;bottom:18px;right:18px;display:flex;gap:6px;z-index:20}}
#controls button{{width:38px;height:38px;border:1px solid #bbb;
  background:rgba(255,255,255,.9);border-radius:8px;cursor:pointer;
  font-size:15px;color:#555;box-shadow:0 1px 4px rgba(0,0,0,.15)}}
#controls button:hover{{background:#fff;color:#222}}
#autospace{{width:auto!important;padding:0 10px;font-size:12px}}
#tip{{position:fixed;background:rgba(255,255,255,.97);border:1px solid #ccc;
  border-radius:9px;padding:7px 13px;font-size:12px;pointer-events:none;display:none;
  box-shadow:0 3px 10px rgba(0,0,0,.18);z-index:100;max-width:220px}}
#tc{{width:100vw;height:100vh;overflow:hidden;user-select:none}}
svg{{width:100%;height:100%;display:block}}
.marriage{{stroke:#888;stroke-width:2;fill:none;stroke-linecap:butt;stroke-linejoin:miter}}
.conn{{stroke:#888;stroke-width:1.8;fill:none;stroke-linecap:butt;stroke-linejoin:miter}}
.sec{{stroke:#e74c3c;stroke-dasharray:6,4}}
.pname{{font-size:10px;font-family:Arial,sans-serif;font-weight:700;
  dominant-baseline:central;text-anchor:middle;fill:#1a1a1a;pointer-events:none}}
.pnick{{font-size:9px;font-family:Arial,sans-serif;font-weight:400;font-style:italic;
  dominant-baseline:central;text-anchor:middle;fill:#555;pointer-events:none}}
.person{{cursor:grab;filter:drop-shadow(1px 2px 3px rgba(0,0,0,.18));transition:filter .1s}}
.person:active{{cursor:grabbing;filter:drop-shadow(2px 4px 8px rgba(0,0,0,.35))}}
</style>
</head>
<body>
<div id="title">Albero Genealogico Gallotta</div>
<div id="legend"><h4>Generazioni</h4>{legend_html}</div>
<div id="tip"></div>
<div id="controls">
  <button id="btn-zi"    title="Zoom +">+</button>
  <button id="btn-zo"    title="Zoom -">−</button>
  <button id="btn-fit"   title="Fit">⌂</button>
  <button id="autospace" title="Risolvi sovrapposizioni">Auto-spazio</button>
</div>
<div id="tc">
  <svg id="tree" xmlns="http://www.w3.org/2000/svg">
    <g id="canvas">
      <g id="conn-layer"></g>
      <g id="box-layer"></g>
    </g>
  </svg>
</div>
<script>
// ── Data from Python ──────────────────────────────────────────────────────────
const P       = {json.dumps(persons_js, ensure_ascii=False)};
const COUPLES = {json.dumps(couples_js, ensure_ascii=False)};
const GEN_META= {json.dumps({str(g): m for g, m in GEN_META.items()}, ensure_ascii=False)};
const BOX_W={BOX_W}, BOX_H={BOX_H}, DROP={CONN_DROP};

// ── SVG helpers ───────────────────────────────────────────────────────────────
const NS='http://www.w3.org/2000/svg';
const connL = document.getElementById('conn-layer');
const boxL  = document.getElementById('box-layer');

function el(tag, attrs){{
  const e = document.createElementNS(NS, tag);
  for(const[k,v] of Object.entries(attrs)) e.setAttribute(k,v);
  return e;
}}

// ── Render ────────────────────────────────────────────────────────────────────
function render(){{
  connL.innerHTML=''; boxL.innerHTML='';
  for(const c of COUPLES) drawCouple(c);
  for(const pid of Object.keys(P)) drawBox(pid);
}}

function drawCouple(c){{
  const {{id,p1,p2,children,secondary}} = c;
  const cls = secondary ? 'sec' : '';
  const d1=P[p1], d2=P[p2];
  if(!d1||!d2) return;

  // ── Marriage line ──────────────────────────────────────────────────────────
  // The line is always drawn exactly between the two box edges.
  const lx = Math.min(d1.x,d2.x)+BOX_W/2;
  const rx = Math.max(d1.x,d2.x)-BOX_W/2;
  const my = (d1.y+d2.y)/2;

  if(rx>lx){{
    connL.appendChild(el('line',{{
      x1:lx, y1:my, x2:rx, y2:my,
      class:`marriage ${{cls}}`
    }}));
  }}

  if(!children.length) return;

  // ── Family connector ───────────────────────────────────────────────────────
  // IMPORTANT: use the marriage-line Y (my), not d1.y.
  // This keeps the vertical and horizontal segments joined even when either
  // spouse is moved independently.
  const pmx = (d1.x+d2.x)/2;
  const startY = my;
  const dropY = startY + BOX_H/2 + DROP;

  // One continuous SVG path is used for the connector.
  // This avoids tiny visual gaps between separate <line> elements and makes
  // every vertical/horizontal intersection an exact geometric junction.
  const path = [];
  path.push(`M ${{pmx}} ${{startY}}`);
  path.push(`V ${{dropY}}`);

  const cxs = children
    .map(k=>P[k]?.x)
    .filter(x=>x!=null)
    .sort((a,b)=>a-b);

  if(cxs.length>1){{
    path.push(`M ${{cxs[0]}} ${{dropY}}`);
    path.push(`H ${{cxs.at(-1)}}`);
  }}

  // Every child vertical starts EXACTLY at the horizontal bar and ends
  // EXACTLY at the top edge of the child box.
  for(const k of children){{
    const pk=P[k];
    if(!pk) continue;
    path.push(`M ${{pk.x}} ${{dropY}} V ${{pk.y-BOX_H/2}}`);
  }}

  connL.appendChild(el('path',{{
    d:path.join(' '),
    class:`conn ${{cls}}`
  }}));
}}

function drawBox(pid){{
  const p=P[pid], gm=GEN_META[p.gen];
  const g=el('g',{{class:'person','data-pid':pid}});
  g.appendChild(el('rect',{{
    x:p.x-BOX_W/2, y:p.y-BOX_H/2, width:BOX_W, height:BOX_H,
    rx:8, ry:8, fill:gm.fill, stroke:gm.stroke, 'stroke-width':2
  }}));
  if(p.nick){{
    const t1=el('text',{{x:p.x,y:p.y-8,class:'pname'}}); t1.textContent=p.label; g.appendChild(t1);
    const t2=el('text',{{x:p.x,y:p.y+9,class:'pnick'}}); t2.textContent=`"${{p.nick}}"`; g.appendChild(t2);
  }}else{{
    const t=el('text',{{x:p.x,y:p.y,class:'pname'}}); t.textContent=p.label; g.appendChild(t);
  }}
  g.addEventListener('mouseenter', e=>showTip(e,pid));
  g.addEventListener('mousemove',  e=>moveTip(e));
  g.addEventListener('mouseleave', hideTip);
  boxL.appendChild(g);
}}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const tip=document.getElementById('tip');
function showTip(e,pid){{
  const p=P[pid], gm=GEN_META[p.gen];
  tip.innerHTML=`<b style="color:${{gm.stroke}}">${{p.label}}</b>`+
    (p.nick?`<br><i>"${{p.nick}}"</i>`:'') +
    `<br><span style="color:#777">Gen.${{p.gen}}</span>`;
  tip.style.display='block'; moveTip(e);
}}
function moveTip(e){{tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY-10)+'px';}}
function hideTip(){{tip.style.display='none';}}

// ── Zoom / pan ────────────────────────────────────────────────────────────────
const tc=document.getElementById('tc');
const canvas=document.getElementById('canvas');
let scale=1,tx=0,ty=0;
function applyT(){{canvas.setAttribute('transform',`translate(${{tx}},${{ty}}) scale(${{scale}})`);}}

function zoom(f,cx,cy){{
  cx=cx??tc.clientWidth/2; cy=cy??tc.clientHeight/2;
  const ns=Math.min(Math.max(scale*f,.06),6);
  tx=cx-(cx-tx)*(ns/scale); ty=cy-(cy-ty)*(ns/scale); scale=ns; applyT();
}}
function fitView(){{
  const xs=Object.values(P).map(p=>p.x);
  const ys=Object.values(P).map(p=>p.y);
  const vw=tc.clientWidth, vh=tc.clientHeight;
  const pad=70;
  const tw=Math.max(...xs)-Math.min(...xs)+BOX_W+pad*2;
  const th=Math.max(...ys)-Math.min(...ys)+BOX_H+pad*2;
  scale=Math.min(vw/tw,vh/th)*.93;
  tx=(vw-(Math.max(...xs)+Math.min(...xs))*scale)/2;
  ty=(vh-(Math.max(...ys)+Math.min(...ys))*scale)/2;
  applyT();
}}

tc.addEventListener('wheel',e=>{{
  e.preventDefault(); zoom(e.deltaY<0?1.12:.89,e.clientX,e.clientY);
}},{{passive:false}});

document.getElementById('btn-zi').onclick=()=>zoom(1.25);
document.getElementById('btn-zo').onclick=()=>zoom(.8);
document.getElementById('btn-fit').onclick=fitView;

// ── Drag / pan ────────────────────────────────────────────────────────────────
let dragPid=null,dragStart=null,isPan=false,panStart=null,rafId=null;

function toSVG(cx,cy){{
  const m=canvas.getScreenCTM().inverse();
  return {{x:cx*m.a+cy*m.c+m.e, y:cx*m.b+cy*m.d+m.f}};
}}

tc.addEventListener('pointerdown',e=>{{
  const pg=e.target.closest('.person');
  if(pg){{
    dragPid=pg.dataset.pid;
    const sv=toSVG(e.clientX,e.clientY);
    dragStart={{mx:sv.x,my:sv.y,ox:P[dragPid].x,oy:P[dragPid].y}};
    tc.setPointerCapture(e.pointerId);
  }}else{{
    isPan=true; panStart={{x:e.clientX,y:e.clientY,tx,ty}};
    tc.setPointerCapture(e.pointerId);
  }}
}});

tc.addEventListener('pointermove',e=>{{
  if(dragPid){{
    const sv=toSVG(e.clientX,e.clientY);
    P[dragPid].x=dragStart.ox+(sv.x-dragStart.mx);
    P[dragPid].y=dragStart.oy+(sv.y-dragStart.my);
    if(!rafId) rafId=requestAnimationFrame(()=>{{render();rafId=null;}});
  }}else if(isPan){{
    tx=panStart.tx+(e.clientX-panStart.x);
    ty=panStart.ty+(e.clientY-panStart.y);
    applyT();
  }}
}});

tc.addEventListener('pointerup',e=>{{
  dragPid=null; dragStart=null; isPan=false; panStart=null;
  tc.releasePointerCapture(e.pointerId);
}});

// ── Auto-space ────────────────────────────────────────────────────────────────
document.getElementById('autospace').onclick=autoSpace;

function autoSpace(){{
  const byY={{}};
  for(const[pid,p] of Object.entries(P)){{
    const k=Math.round(p.y); (byY[k]||(byY[k]=[])).push(pid);
  }}
  const MIN=BOX_W+8;
  for(const pids of Object.values(byY)){{
    pids.sort((a,b)=>P[a].x-P[b].x);
    // Forward pass: push right
    for(let i=1;i<pids.length;i++){{
      if(P[pids[i]].x-P[pids[i-1]].x<MIN)
        P[pids[i]].x=P[pids[i-1]].x+MIN;
    }}
    // Backward pass: push left
    for(let i=pids.length-2;i>=0;i--){{
      if(P[pids[i+1]].x-P[pids[i]].x<MIN)
        P[pids[i]].x=P[pids[i+1]].x-MIN;
    }}
  }}
  render(); fitView();
}}

// ── Init ──────────────────────────────────────────────────────────────────────
render();
autoSpace();   // resolve any initial overlaps, then fit
</script>
</body>
</html>"""

Path(HTML_FILE).write_text(html, encoding="utf-8")
if AUTO_OPEN:
    webbrowser.open(Path(HTML_FILE).resolve().as_uri())