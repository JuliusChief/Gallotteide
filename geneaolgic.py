import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from collections import defaultdict

INPUT_FILE = "Albero_Genealogico_Gallotta.xlsx"
HTML_FILE  = "albero_gallotta.html"
AUTO_OPEN  = True

# Spacing
H_UNIT = 3.0   # horizontal distance between the two spouses
H_PAD  = 2.0   # minimum padding between adjacent families
V_GAP  = 5.0   # vertical distance between generations

# ── 1. LOAD ──────────────────────────────────────────────────────────────────
df_p = pd.read_excel(INPUT_FILE, sheet_name="Persone")
df_r = pd.read_excel(INPUT_FILE, sheet_name="Relazioni")

persons = {}
for _, r in df_p.iterrows():
    label = f"{r.nome} {r.cognome}"
    if pd.notna(r.soprannome) and str(r.soprannome).strip():
        label += f' "{r.soprannome}"'
    persons[int(r.person_id)] = {
        "label":   label,
        "nome":    str(r.nome),
        "cognome": str(r.cognome),
        "gen":     int(r.generazione),
    }

person_spouses = defaultdict(list)   # pid → [spouses, ordered by first appearance]
seen_marriages = set()
all_marriages  = []
parents_of     = defaultdict(list)   # child → [parents]
children_of    = defaultdict(list)   # parent → [children]

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

# Shared children of each couple
couple_children = {}
for m in all_marriages:
    p1, p2 = m
    couple_children[m] = sorted(set(children_of[p1]) & set(children_of[p2]))

# Primary couple key for each person (first marriage encountered)
primary_couple = {}
for pid, sp_list in person_spouses.items():
    primary_couple[pid] = tuple(sorted([pid, sp_list[0]]))

# ── 2. TREE STRUCTURE ────────────────────────────────────────────────────────
def tree_children(ck):
    """Ordered child couple-keys of ck (following primary couples)."""
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

# All couple-keys (including single-parent where relevant)
all_ck = set(all_marriages)
for pid in persons:
    if not person_spouses[pid]:
        ck_single = (pid,)
        if tree_children(ck_single):
            all_ck.add(ck_single)

# Root couple-keys: no member has parents in the dataset
root_cks = sorted(
    [ck for ck in all_ck if all(not parents_of.get(p) for p in ck)],
    key=lambda ck: ck[0],
)

# ── 3. SUBTREE WIDTHS ────────────────────────────────────────────────────────
_w = {}

def subtree_width(ck):
    if ck in _w:
        return _w[ck]
    kids = tree_children(ck)
    min_w = len(ck) * H_UNIT + H_PAD
    # Extra width for secondary marriages of couple members
    sec_extra = 0
    for p in ck:
        for sec_sp in person_spouses[p][1:]:
            sec_key = tuple(sorted([p, sec_sp]))
            n_sec_kids = len(couple_children.get(sec_key, []))
            sec_extra += (n_sec_kids + 1) * H_UNIT + H_PAD
    w = (max(sum(subtree_width(c) for c in kids), min_w) if kids else min_w) + sec_extra
    _w[ck] = w
    return w

# ── 4. ASSIGN POSITIONS ──────────────────────────────────────────────────────
pos = {}   # pid → (x, y)

def place(ck, cx, y):
    # Position this couple's two members
    if len(ck) == 2:
        pos[ck[0]] = (cx - H_UNIT / 2, y)
        pos[ck[1]] = (cx + H_UNIT / 2, y)
    else:
        pos[ck[0]] = (cx, y)
    kids = tree_children(ck)
    if not kids:
        return
    # Total width of primary children (exclude secondary-marriage extra)
    sec_extra = sum(
        (len(couple_children.get(tuple(sorted([p, sec_sp])), [])) + 1) * H_UNIT + H_PAD
        for p in ck
        for sec_sp in person_spouses[p][1:]
    )
    prim_total = sum(subtree_width(c) for c in kids) - sec_extra
    # Centre the children block under this couple, reserving extra space at right
    x = cx - (prim_total + sec_extra) / 2
    for c in kids:
        # Use the raw (non-secondary-expanded) width for primary children
        w = subtree_width(c)
        # Subtract secondary extras contributed by c's own members
        own_extra = sum(
            (len(couple_children.get(tuple(sorted([p2, sec_sp])), [])) + 1) * H_UNIT + H_PAD
            for p2 in c
            for sec_sp in person_spouses[p2][1:]
        )
        place(c, x + (w - own_extra) / 2, y - V_GAP)
        x += w

x_off = 0
for rck in root_cks:
    w = subtree_width(rck)
    place(rck, x_off + w / 2, 0)
    x_off += w + H_PAD * 2

# Post-process: place secondary spouses and their children
for pid, sp_list in person_spouses.items():
    if len(sp_list) < 2 or pid not in pos:
        continue
    px, py = pos[pid]
    for sec_sp in sp_list[1:]:
        if sec_sp in pos:
            continue
        # Anchor secondary spouse just right of rightmost node at this y-level
        same_y_xs = [v[0] for v in pos.values() if abs(v[1] - py) < 0.1]
        sec_x = (max(same_y_xs) + H_UNIT + H_PAD) if same_y_xs else (px + H_UNIT)
        pos[sec_sp] = (sec_x, py)
        # Place secondary children
        sec_key = tuple(sorted([pid, sec_sp]))
        sec_kids = couple_children.get(sec_key, [])
        mid_x = (px + sec_x) / 2
        for i, kid in enumerate(sec_kids):
            if kid not in pos:
                pos[kid] = (
                    mid_x + (i - (len(sec_kids) - 1) / 2) * H_UNIT,
                    py - V_GAP,
                )

# ── 5. BUILD PLOTLY TRACES ────────────────────────────────────────────────────
GEN_COLORS = {
    1: "#c0392b",
    2: "#2471a3",
    3: "#1e8449",
    4: "#7d3c98",
    5: "#d68910",
}

# ── Edge traces (marriage lines + tree connectors) ──
primary_lx, primary_ly = [], []   # primary marriage lines & tree connectors
secondary_lx, secondary_ly = [], []  # secondary marriage lines

def seg(lx, ly, x0, y0, x1, y1):
    lx.extend([x0, x1, None])
    ly.extend([y0, y1, None])

done = set()

def draw_connectors(ck):
    if ck in done:
        return
    done.add(ck)

    # Marriage line between the two spouses
    if len(ck) == 2 and all(p in pos for p in ck):
        seg(primary_lx, primary_ly, pos[ck[0]][0], pos[ck[0]][1],
            pos[ck[1]][0], pos[ck[1]][1])

    kids = tree_children(ck)
    if not kids:
        return

    # Parent midpoint
    if len(ck) == 2 and all(p in pos for p in ck):
        pmx = (pos[ck[0]][0] + pos[ck[1]][0]) / 2
        pmy = pos[ck[0]][1]
    elif ck[0] in pos:
        pmx, pmy = pos[ck[0]]
    else:
        for c in kids:
            draw_connectors(c)
        return

    # Midpoints of child couples
    child_mids = []
    for c in kids:
        if len(c) == 2 and all(p in pos for p in c):
            cmx = (pos[c[0]][0] + pos[c[1]][0]) / 2
            cmy = pos[c[0]][1]
        elif c[0] in pos:
            cmx, cmy = pos[c[0]]
        else:
            continue
        child_mids.append((cmx, cmy))

    if not child_mids:
        for c in kids:
            draw_connectors(c)
        return

    child_y = child_mids[0][1]
    drop_y  = (pmy + child_y) / 2

    # Vertical drop from parent midpoint
    seg(primary_lx, primary_ly, pmx, pmy, pmx, drop_y)
    # Horizontal sibling bar
    xs = sorted(m[0] for m in child_mids)
    seg(primary_lx, primary_ly, xs[0], drop_y, xs[-1], drop_y)
    # Vertical drops to each child couple midpoint
    for cmx, cmy in child_mids:
        seg(primary_lx, primary_ly, cmx, drop_y, cmx, cmy)

    for c in kids:
        draw_connectors(c)

for rck in root_cks:
    draw_connectors(rck)

# Secondary marriage lines and their child connectors
for pid, sp_list in person_spouses.items():
    if len(sp_list) < 2:
        continue
    for sec_sp in sp_list[1:]:
        if pid not in pos or sec_sp not in pos:
            continue
        seg(secondary_lx, secondary_ly,
            pos[pid][0], pos[pid][1], pos[sec_sp][0], pos[sec_sp][1])
        sec_key = tuple(sorted([pid, sec_sp]))
        sec_kids = [k for k in couple_children.get(sec_key, []) if k in pos]
        if sec_kids:
            pmx = (pos[pid][0] + pos[sec_sp][0]) / 2
            pmy = pos[pid][1]
            child_y = pos[sec_kids[0]][1]
            drop_y  = (pmy + child_y) / 2
            seg(secondary_lx, secondary_ly, pmx, pmy, pmx, drop_y)
            xs = sorted(pos[k][0] for k in sec_kids)
            seg(secondary_lx, secondary_ly, xs[0], drop_y, xs[-1], drop_y)
            for k in sec_kids:
                seg(secondary_lx, secondary_ly, pos[k][0], drop_y, pos[k][0], pos[k][1])

edges_primary = go.Scatter(
    x=primary_lx, y=primary_ly,
    mode="lines",
    line=dict(width=1.5, color="#666666"),
    hoverinfo="none",
)
edges_secondary = go.Scatter(
    x=secondary_lx, y=secondary_ly,
    mode="lines",
    line=dict(width=1.5, color="#e74c3c", dash="dash"),
    hoverinfo="none",
    name="Secondo matrimonio",
)

# ── Node trace ──
nx_l, ny_l, node_text, hover_text, node_colors, node_symbols = [], [], [], [], [], []

for pid, info in sorted(persons.items()):
    if pid not in pos:
        continue
    x, y = pos[pid]
    nx_l.append(x)
    ny_l.append(y)
    node_text.append(info["label"])
    hover_text.append(
        f"<b>{info['label']}</b><br>"
        f"Generazione {info['gen']}"
    )
    node_colors.append(GEN_COLORS.get(info["gen"], "#888888"))

nodes = go.Scatter(
    x=nx_l, y=ny_l,
    mode="markers+text",
    text=node_text,
    hovertext=hover_text,
    hoverinfo="text",
    textposition="top center",
    textfont=dict(size=9, family="Arial"),
    marker=dict(
        size=14,
        color=node_colors,
        line=dict(width=2, color="white"),
    ),
)

# ── Legend entries (one per generation) ──
legend_traces = [
    go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(size=10, color=color),
        name=f"Generazione {gen}",
        showlegend=True,
    )
    for gen, color in sorted(GEN_COLORS.items())
    if any(info["gen"] == gen for info in persons.values())
]

# ── 6. FIGURE ────────────────────────────────────────────────────────────────
fig = go.Figure(
    data=[edges_primary, edges_secondary, nodes] + legend_traces,
    layout=go.Layout(
        title=dict(
            text="Albero Genealogico Gallotta",
            x=0.5, xanchor="center",
            font=dict(size=26, family="Georgia, serif"),
        ),
        showlegend=True,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="#ccc", borderwidth=1),
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   fixedrange=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   fixedrange=False),
        plot_bgcolor="white",
        paper_bgcolor="#f5f5f0",
        margin=dict(l=20, r=20, t=70, b=20),
    ),
)

pio.write_html(
    fig,
    file=HTML_FILE,
    auto_open=AUTO_OPEN,
    include_plotlyjs=True,
)