# Capacity Estimation

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

- **Home** (`/`) — capacity-vs-estimate overview per person (available vs. workstream
  allocation vs. open task estimates, with an over-allocation flag). Reserved for more
  visualisations later.
- **People / Strategy / Workstreams / Tasks** — create and amend records. Tasks can be
  filtered by workstream, person, and status. Each **person** row has a **timeline** view
  comparing estimated vs. actual dates across their tasks; each **workstream** row has a
  timeline of its constituent tasks' estimated dates — both are ECharts Gantt-style charts.
- **Capacity** (`/capacity`) — tabbed CRUD for planning periods, per-member availability,
  and workstream allocations.
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
  services.py # estimate_history logging helpers
  main.py     # NiceGUI entrypoint + page routes
  pages/      # home, people, strategy, workstreams, tasks, capacity
data/         # seed CSVs (incl. capacity_period, team_member_capacity, workstream_allocation)
tests/        # seed round-trip, history logging, capacity summary, timeline chart builders
```

## Notes

Task effort is a single per-task total (`estimated_effort_weeks`); it is not yet phased
across periods, so the capacity-vs-estimate overview compares period-summed availability
and allocation against total open task effort per person.
