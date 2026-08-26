# Design & Code Standards

Conventions for this project. These are descriptive of what's already in the
codebase (so new code stays consistent with it) plus a few forward-looking rules
for areas the project is about to grow into (visualisations). See
[architecture.md](architecture.md) for *why* the system is shaped this way;
this document is about *how* to write the next piece of it.

## Code standards

### Module layout

Each `app/pages/<entity>.py` follows the same shape, top to bottom:

1. Module docstring — one line, states what the page does.
2. `COLUMNS` — the `ui.table` column spec as a module-level constant.
3. `_load_rows(...)` — query the DB, return a flat `list[dict]` shaped for `ui.table`.
4. `_save(...)` — upsert, called from the dialog's Save handler.
5. `build()` — the page entrypoint registered in `app/main.py`; renders the
   header, controls, table, and defines `refresh()` / `open_form()` as closures.

Keep new CRUD pages in this shape rather than inventing a new structure — see
[people.py](../app/pages/people.py) for the shortest example and
[tasks.py](../app/pages/tasks.py) for one with filters and a secondary
(history) dialog. When a page hosts multiple near-identical CRUD tables or
entities, factor the shared table/dialog scaffolding into a helper rather than
copy-pasting the pattern per entity — see `_render_workstream_table()` in
[workstreams.py](../app/pages/workstreams.py), which renders the same workstream
table (with its `edit`/`timeline` actions) once per strategy-item card plus
once more for the "Unassigned" bucket, instead of duplicating that table
definition at every call site.

### Naming

- `snake_case` for functions and variables, `PascalCase` for ORM model classes.
- Module-private helpers (not part of a page's public `build()` entrypoint) get
  a leading underscore: `_load_rows`, `_save`, `_crud_panel`.
- Table/query result dicts use the same field names as the ORM column
  (`estimated_effort_weeks`, not `effort` or `weeks`) so a glance at a
  `COLUMNS` spec tells you the source column. FK display fields are the
  resolved name appended without a suffix (`workstream`, not `workstream_name`);
  the raw FK id is kept alongside it as `<fk>_id` for filtering/editing (see
  `_load_rows()` in [tasks.py](../app/pages/tasks.py)).
- Sentinel values get a leading/trailing dunder-free underscore constant, e.g.
  `_ALL = "__all__"` in `tasks.py` for "no filter selected" — never reuse
  `None` for this since `None` is also a legitimate FK value (unassigned).

### Typing & style

- `from __future__ import annotations` at the top of every module; use modern
  union syntax (`int | None`), not `Optional[int]`.
- SQLAlchemy 2.0 typed ORM style only: `Mapped[...]` + `mapped_column(...)`.
  Don't mix in the legacy `Column(...)` style.
- Docstrings: one-line module docstring is required; function docstrings only
  when the *why* isn't obvious from the name and signature (see the repo-wide
  comment policy — this project follows it strictly). Most `_load_rows` /
  `_save` functions have no docstring; `capacity_summary()` has one because its
  return shape and the closed-vs-open task distinction aren't obvious from the
  signature.
- No comments that restate what the code does. A comment is only for a
  non-obvious constraint — e.g. the `StaticPool` comment in `db.py`, or the
  "parents before children" comment on `CSV_TABLES` in `seed.py`.

### Data access

- Every DB operation opens its own session via `with get_session() as session:`
  and lets the context manager commit/rollback — never hold a session open
  across a NiceGUI callback boundary or store one on `self`/module state.
- Query results that feed a `ui.table` are converted to plain dicts *inside*
  the `with` block, before the session closes (SQLAlchemy objects are
  `expire_on_commit=False` but still shouldn't be handed to the UI layer
  directly — dicts keep the page layer decoupled from ORM internals).
- FK dropdown option lists (`member_options()`, `workstream_options()`, etc. in
  [common.py](../app/pages/common.py)) are re-queried on every dialog open
  rather than cached — see [architecture.md](architecture.md#6-session-per-call-data-access)
  for why. Don't add caching here without also solving invalidation; a stale
  FK dropdown is a worse bug than an extra query.
- Business logic that doesn't touch NiceGUI — history logging, rollups,
  anything you'd want to unit test without a browser — belongs in
  `app/services.py`, not inline in a page's `build()`. If you're writing a
  `for` loop with `sum()`/`filter` logic inside a page function, stop and ask
  whether it belongs in services instead.

### Testing

- New service functions get a test in `tests/` using the `session` fixture
  from [conftest.py](../tests/conftest.py) (fresh in-memory DB per test) —
  follow `test_capacity.py`'s pattern of building minimal fixture rows inline
  rather than depending on `data/*.csv` seed content, so tests don't break when
  seed data changes.
- Tests that *do* depend on seed content (`test_seed.py`) call `load_csvs()`
  explicitly and assert on counts/round-trip equality, not on specific seeded
  names/values — seed data is content, not a test fixture contract.
- Pages are not unit tested. Verify new/changed pages by running the app
  (`uv run python -m app.main`) and exercising them in a browser — this project
  uses the Claude Code browser-preview tooling for that; there's no Selenium/
  Playwright harness to maintain.

## Design standards (UI)

The UI is built entirely from NiceGUI's default Quasar component set — no
custom CSS files, no design tokens, no component library beyond what NiceGUI
ships. Consistency comes from reusing the same handful of patterns everywhere:

- **Page chrome:** every page calls `header(<active-label>)` from
  [layout.py](../app/pages/layout.py) first, which renders the shared nav bar
  and the Export-to-CSV action. Don't build a page without it.
- **Layout:** wrap page content in `ui.column().classes("w-full p-4 gap-4")` (or
  `gap-2` for denser pages like Capacity). Section headers are
  `ui.label(...).classes("text-xl font-bold")` (page title) or `text-2xl
  font-bold` (Home's top-level heading only).
- **Tables:** `ui.table(columns=COLUMNS, rows=rows, row_key="id").classes("w-full")`.
  `COLUMNS` is always a module-level list of `{"name", "label", "field",
  "align"}` dicts; numeric columns omit `align` (defaults to right-aligned),
  text columns get `"align": "left"`. A trailing `actions` column with an empty
  label hosts row buttons via a `body-cell-actions` slot.
- **Row actions:** dense flat icon buttons (`q-btn dense flat icon="edit"`)
  emitting a named event (`edit`, `history`) that the page handles with
  `table.on("edit", lambda e: open_form(e.args))`. Don't wire row actions any
  other way (no inline `on_click` per row, which breaks table virtualization).
- **Forms:** always a `ui.dialog()` + `ui.card()`, opened via `dialog.open()`
  at the end of a builder function. One builder function serves both add and
  edit (`row = row or {}`; empty dict means "add"). Card width is `w-96` for
  simple forms, `w-[32rem]`+ for forms with more fields (tasks). Buttons are
  right-aligned (`ui.row().classes("justify-end w-full")`): flat "Cancel" then
  filled "Save", in that order.
- **Feedback:** `ui.notify(..., type="positive")` on successful save,
  `type="negative"` for validation failures. No custom toast/snackbar.
- **Status colour:** every `status` table column (strategy items, workstreams,
  tasks) renders through the shared `STATUS_BADGE_SLOT` from
  [app/pages/common.py](../app/pages/common.py) — a coloured dot + the status
  text, bound to a per-row `status_color` field
  (`STATUS_COLORS.get(row["status"], STATUS_COLOR_FALLBACK)`, set in
  `_load_rows()`). Wire a new status column the same way:
  1. Add `"status_color": STATUS_COLORS.get(x.status, STATUS_COLOR_FALLBACK)`
     to the row dict in `_load_rows()`.
  2. `table.add_slot("body-cell-status", STATUS_BADGE_SLOT)` right after
     creating the `ui.table` (order relative to the `body-cell-actions` slot
     doesn't matter).
  Don't invent a second status-colour scheme — if a status value isn't in
  `STATUS_COLORS` yet, add it there (see the `proposed`/`active`/`on_hold`
  entries added for strategy items) rather than colouring it ad hoc.
  For a condition that isn't a `status` column at all (e.g. Home's
  over-allocation flag), a `q-badge` with `color` bound to the condition is
  the pattern instead — it doesn't need the shared slot's per-row colour
  binding since there are only two states.
- **A second coloured-dot column (e.g. task priority):** the slot markup
  itself is generated by `dot_badge_slot(color_field, text_field)` in
  [common.py](../app/pages/common.py) — `STATUS_BADGE_SLOT` and
  `PRIORITY_BADGE_SLOT` are both just calls to it with different field names,
  so a third one (say, a `severity` column) is `dot_badge_slot("severity_color",
  "severity")`, not a hand-copied HTML string. Give it its **own** colour map
  (`PRIORITY_COLORS`, not a second use of `STATUS_COLORS`) when the new
  column can appear in the *same row* as an existing coloured-dot column —
  `PRIORITY_COLORS` deliberately picked hex values that don't collide with
  any `STATUS_COLORS` value (`test_priority_colors_are_distinct_from_status_colors`
  in [tests/test_common.py](../tests/test_common.py) checks this), so a red
  "blocked" status dot and a red "high" priority dot never look like they're
  reporting the same thing.

## Visualisations: use ECharts via NiceGUI

**Rule:** all charts/visualisations in this project use **Apache ECharts**
through NiceGUI's built-in `ui.echart()` element — not matplotlib, not a
custom SVG/D3 build, not another charting library. This is required starting
with the Home page's planned visualisations and applies to any future chart
anywhere in the app.

Why: `ui.echart` is bundled with NiceGUI (no extra dependency beyond what's
already installed), renders as a native Vue/Quasar component so it participates
in NiceGUI's normal update cycle, and pushes ECharts' full option surface
(bar/line/pie/treemap/heatmap/gauge, etc.) without writing any JavaScript.

### How to use it

```python
from nicegui import ui

chart = ui.echart({
    "xAxis": {"type": "category", "data": ["Alice", "Ben", "Priya", "Diego"]},
    "yAxis": {"type": "value"},
    "series": [{"type": "bar", "name": "Remaining (wks)", "data": [16, 6.5, 3.8, 9.5]}],
}).classes("w-full h-80")
```

**Worked examples:** [app/pages/workstreams.py](../app/pages/workstreams.py)'s
`build_timeline_options()` renders each workstream's tasks as a Gantt-style
timeline (ECharts has no native Gantt series, so it uses the standard
invisible-offset + visible-duration stacked-bar workaround). It's a good
reference for the pattern above — a pure, page-colocated builder function unit
tested in [tests/test_timeline.py](../tests/test_timeline.py) — and for one
sharp edge: **ECharts escapes `{b}`/`{c}`-style tooltip template
substitutions**, so embedding HTML tags (`<br/>`, `<b>`) in a data point's
`name` renders as literal text instead of formatting. Use `\n` plus
`tooltip.extraCssText: "white-space:pre-line"` for multi-line tooltip content
instead of HTML.

[app/pages/people.py](../app/pages/people.py)'s `build_person_timeline_options()`
extends the same technique to compare **estimated vs. actual** dates per task:
two distinct `stack` groups ("est", "act") on the same category axis render as
grouped bars — a full-width bar coloured by status, and a thinner fixed-colour
bar alongside it — with `None` entries where a task is missing one of the two
date pairs so its bar simply doesn't render. `STATUS_COLORS` and
`month_year_axis_label()` both live in
[app/pages/common.py](../app/pages/common.py) since they're now used by both
timelines — a concrete instance of "promote to `common.py` only once two pages
actually need it," not before.

`month_year_axis_label()` is also the project's one deliberate use of embedded
JS in a chart: a numeric 'value' xAxis (which the offset/duration stacking
technique requires) has no native date-aware tick formatting, so it bakes a
small formatter function — via NiceGUI's `":"` dynamic-property convention —
that adds each tick's day offset to a reference date and renders "MMM-YY".
Two things matter if you touch it: use only `getUTC*`/`setUTC*` Date methods
(local-time methods would make the label depend on the *viewer's* browser
timezone, not the server's), and keep `minInterval: 31` — no month has more
than 31 days, so that's what guarantees two consecutive ticks never land in
the same month and repeat a label.

[app/pages/people.py](../app/pages/people.py)'s
`build_allocation_heatmap_options()` is a third pattern: a plain (non-Gantt)
ECharts `heatmap` series on category x/y axes — one row per person, one
column per calendar week, cell coloured by `app.services.weekly_allocation()`.
Two things worth reusing: it builds a **dense grid** (every person x every
week gets a cell, defaulting to 0 where the service returned nothing) so the
chart is rectangular even though the underlying data is sparse; and it
**clamps the cell's colour value** (`min(pct, HEATMAP_MAX)`) while leaving the
*tooltip* text uncapped — relying on `visualMap`'s `outOfRange` styling for a
value that exceeds `max` is fragile (it defaults to a washed-out grey rather
than the intended "hot" colour), so clamp the value going into the chart
instead of trusting the visualMap boundary.

[app/pages/home.py](../app/pages/home.py)'s
`build_workstream_person_grid_options()` is the same heatmap pattern with two
differences worth noting if you build a fourth one: when the value has no
natural ceiling to clamp against (effort-weeks here, vs. a % that clamps at a
fixed `HEATMAP_MAX`), compute `visualMap.max` from the actual data instead
(`max(1, ceil(max(values)))` — the floor of 1 avoids a degenerate 0-0 scale
when nothing has any effort yet); and its axes are transposed on purpose
(people as `xAxis` columns, the grouping entity — workstreams — as `yAxis`
rows) to match how the feature was asked for, whereas the People page's own
heatmap put people on `yAxis`. There's no fixed rule for which entity goes on
which axis — pick whichever reads as "columns vs. rows" the way the request
described it, and keep the `yAxis.inverse: True` convention (first row of the
underlying table renders at the top) regardless of which entity that ends up
being. Both heatmaps set `visualMap.calculable: False` — the legend is
colour-reference only, not a draggable range filter; there was no reason a
viewer dragging the scale should silently change what's "hot" on a shared
dashboard view. Only flip it to `True` for a specific, deliberate reason.

[app/pages/home.py](../app/pages/home.py)'s
`build_team_capacity_chart_options()` is a different shape entirely: an
ordinary stacked **bar** chart (one series per strategy item, all sharing
`stack: "capacity"`) with a `line` series overlaid unstacked, from
`app.services.team_capacity_by_month()`. Because it's a standard multi-series
chart on a category x-axis — not the offset/duration Gantt hack or a
`heatmap` series — it uses a plain `tooltip: {"trigger": "axis"}` and gets
ECharts' default multi-series tooltip for free, with no manually-built `{b}`
template and none of that pattern's HTML-escaping gotcha to worry about.
Reach for this shape (axis-trigger tooltip, ordinary bar/line series) by
default; only build a manual item tooltip when the chart needs one of the two
tricks above (Gantt positioning or a dense matrix) that a plain category axis
can't express.

- Build the `options` dict from data already assembled by an `app/services.py`
  function (e.g. `capacity_summary()`) — never query the DB inside a chart
  builder; keep the same page → services → db layering as everywhere else.
- To refresh a chart after data changes, mutate `chart.options` in place and
  call `chart.update()`, rather than destroying and recreating the element —
  this matches the `refresh()` pattern already used for tables.
- Keep chart option dicts colocated with the page that renders them unless two
  pages need the same chart shape, in which case factor a small
  `build_<x>_options(rows: list[dict]) -> dict` function into the page module
  (not into `services.py`, which stays presentation-agnostic) so it stays unit
  testable by feeding it fixture data and asserting on the resulting dict.
- Size charts with Tailwind/Quasar utility classes (`classes("w-full h-80")`)
  the same way tables and cards are sized — don't set fixed pixel dimensions in
  the options dict.
- Prefer ECharts' built-in tooltip/legend/grid options over building custom
  NiceGUI controls around the chart; only reach for `on_point_click`/`on_click`
  handlers when a chart needs to drive navigation or filtering elsewhere on
  the page.
