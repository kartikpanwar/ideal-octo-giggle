# On My Plate

A NiceGUI app for estimating team capacity against planned work, organised as
**strategy items → workstreams → tasks**, with each task assigned to a team member.

- **Data model:** see [docs/data-model.md](docs/data-model.md).
- **Architecture:** see [docs/architecture.md](docs/architecture.md) for the material
  components and design decisions behind the system.
- **Design & code standards:** see [docs/standards.md](docs/standards.md) before adding
  pages, services, or visualisations.
- **Storage:** in-memory SQLite (SQLAlchemy ORM), seeded from CSV files in `data/` on
  every start. Use **Export to CSV** in the app to write the current DB back to `data/`.
- **History:** amending a task's status or estimated dates appends a snapshot to
  `estimate_history`, including a free-text status update.

## Requirements

- Python 3.12 (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/)

## Run

```bash
uv sync
uv run python -m app.main
```

Then open http://localhost:8080.

## Pages

- **Home** (`/`) — a KPI row (tasks in progress/blocked, active workstreams, people
  over-allocated), a **team capacity chart** (a stacked bar per month, one segment per
  strategy item, showing team time in person-weeks going toward each — plus a dashed line
  for total team available time, so allocation can be read against actual capacity; unlike
  the other visualisations this includes tasks of every status, so past months stay
  populated), and a **workstream x person grid**: workstreams as rows, people as columns,
  each cell coloured by that person's total *open* (not done/cancelled) estimated effort on
  tasks in that workstream — an at-a-glance "who's working on what".
- **People** (`/people`) — team member CRUD (name, role, weekly hours, active, active-from
  date; no email field). Each row shows an initials avatar (colour stable per person). Each
  row's **timeline** view compares estimated vs. actual dates across that person's tasks,
  and the page also has a **weekly allocation heatmap**: one row per person, one column per
  calendar week, coloured by % of that week's capacity consumed by estimated task effort
  (spread evenly across each task's date range).
- **Workstreams** (`/workstreams`) — strategy items and their workstreams on one page: each
  strategy item is a card with its workstreams listed underneath (plus an "Unassigned" card
  for workstreams with no strategy item), with a multi-select status filter for the
  workstream lists. Each workstream row has a **timeline** of its constituent tasks'
  estimated dates — an ECharts Gantt-style chart, same technique as the People page's
  per-person timeline.
- **Tasks** (`/tasks`) — task CRUD, including actual start/end dates alongside the estimated
  ones and a **priority** field (low/medium/high, defaults to medium). Filterable by
  workstream, person, and status (status is multi-select, defaulting to everything except
  done/cancelled).
- Every status column (strategy items, workstreams, tasks) renders as a coloured dot +
  label rather than plain text, using a shared status → colour map; task priority uses the
  same coloured-dot pattern with its own (deliberately distinct) traffic-light palette.
- **Export to CSV** (header button) — write the in-memory DB back to `data/*.csv`.

## Test

```bash
uv run pytest
```

## Project layout

```
app/
  db.py       # in-memory engine + session
  models.py   # SQLAlchemy models (full data model)
  seed.py     # CSV <-> DB load/export
  services.py # estimate_history logging, capacity/KPI/allocation rollups
  main.py     # NiceGUI entrypoint + page routes
  pages/      # home, people, workstreams (incl. strategy items), tasks
              # (layout.py holds the shared header/nav, app name, and icon)
data/         # seed CSVs (incl. capacity_period, team_member_capacity, workstream_allocation —
              # those three tables have no CRUD page but are still seeded/used by services;
              # and estimate_history with a few sample estimate revisions)
tests/        # seed round-trip, history logging, capacity/KPI summaries, timeline & chart builders
```

## Notes

Task effort is a single per-task total (`estimated_effort_weeks`); it is not yet phased
across periods. `capacity_summary()` (behind Home's "people over-allocated" KPI) compares
period-summed availability/allocation against *total* open task effort per person rather
than per period, and the People page's weekly heatmap approximates a weekly figure by
spreading each task's total evenly across the calendar weeks it spans.
