import pandas as pd
import networkx as nx
import dash
from dash import dcc, html
import plotly.graph_objects as go

# --- LOAD DATA ---
df_p = pd.read_excel("Albero_Genealogico_Gallotta.xlsx", sheet_name="Persone")
df_r = pd.read_excel("Albero_Genealogico_Gallotta.xlsx", sheet_name="Relazioni")

# --- BUILD GRAPH ---
G = nx.DiGraph()

for _, r in df_p.iterrows():
    G.add_node(
        r.person_id,
        label=f"{r.nome} {r.cognome}",
        gen=r.generazione
    )

for _, r in df_r[df_r.tipo == "genitore"].iterrows():
    G.add_edge(r.person_id_1, r.person_id_2)

# --- COMPUTE POSITIONS ---
pos = {}
gen_groups = df_p.groupby("generazione")

for gen, group in gen_groups:
    y = gen
    xs = list(range(len(group)))
    for x, pid in zip(xs, group.person_id):
        pos[pid] = (x, y)

# --- EDGES ---
edge_x, edge_y = [], []
for a, b in G.edges():
    x0, y0 = pos[a]
    x1, y1 = pos[b]
    edge_x += [x0, x1, None]
    edge_y += [y0, y1, None]

edges = go.Scatter(
    x=edge_x,
    y=edge_y,
    mode="lines",
    line=dict(width=1),
    hoverinfo="none"
)

# --- NODES ---
node_x = [pos[n][0] for n in G.nodes()]
node_y = [pos[n][1] for n in G.nodes()]
labels = [G.nodes[n]["label"] for n in G.nodes()]

nodes = go.Scatter(
    x=node_x,
    y=node_y,
    mode="markers+text",
    text=labels,
    textposition="top center",
    marker=dict(size=10),
)

# --- MARRIAGE EDGES ---
marriage_x, marriage_y = [], []

for _, r in df_r[df_r.tipo == "matrimonio"].iterrows():
    p1, p2 = r.person_id_1, r.person_id_2

    # skip if someone has no position (safety)
    if p1 not in pos or p2 not in pos:
        continue

    x0, y0 = pos[p1]
    x1, y1 = pos[p2]

    marriage_x += [x0, x1, None]
    marriage_y += [y0, y1, None]

marriages = go.Scatter(
    x=marriage_x,
    y=marriage_y,
    mode="lines",
    line=dict(width=3, dash="solid"),
    hoverinfo="none"
)


# --- DASH APP ---
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H3("Albero Genealogico Gallotta"),
    dcc.Graph(
    style={"height": "95vh", "width": "100vw"},
    figure=go.Figure(
        data=[edges, marriages, nodes],
        layout=go.Layout(
            yaxis=dict(autorange="reversed"),
            showlegend=False,
            width=4000,
            height=2400,
        )
    )
)])

if __name__ == "__main__":
    app.run(debug=True)