# Gallotteide

Interactive family tree of the Gallotta family.

Open `docs/index.html` in a browser (double-click works, no server needed) to explore the tree. It is drawn like a real tree: the oldest generation sits on the trunk at the bottom, and each generation grows upwards on tapering branches with leaves.

- **Overview first**: the tree opens on the first two generations, one coloured branch per line of descendants. Click a `+N` button under a couple to open that branch, `−` to close it again.
- **Click a person** to see their parents, spouses, children and siblings, and to highlight their whole line (ancestors and descendants) in gold. Names in the panel are links.
- **Search** by first name, surname or nickname (press `/` to jump to the search box).
- **Legend**: click a branch to open and frame it.
- **Navigate** by dragging, scrolling or pinching to zoom; the buttons bottom-left zoom, fit the tree, expand everything or go back to the overview.
- Works on phones and follows the system light/dark theme.

## Updating the data

The data lives in `Albero_Genealogico_Gallotta.xlsx`:

| Sheet | Columns |
| --- | --- |
| `Persone` | `person_id`, `nome`, `cognome`, `soprannome`, `generazione` |
| `Relazioni` | `rel_id`, `tipo` (`matrimonio` or `genitore`), `person_id_1`, `person_id_2` |

For `genitore`, `person_id_1` is the parent and `person_id_2` the child.

After editing the workbook, rebuild the data file used by the page:

```bash
pip install -r requirements.txt
python genealogic.py          # writes docs/data.js
python genealogic.py --open   # same, then opens the tree
```

The script also prints warnings for inconsistent data (unknown ids, duplicated relations, generations that don't follow their parents, people not connected to anyone) and lists the people who start a separate branch because their parents are missing.

## Publishing

The `docs/` folder is a self-contained static site, so it can be published with GitHub Pages (Settings → Pages → Deploy from branch → `main` / `docs`).
