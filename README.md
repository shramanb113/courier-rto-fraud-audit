# Courier Telemetry Audit & RTO Fraud Analytics Engine

A local-first Python system for auditing courier delivery telemetry and
surfacing likely fraudulent "Return to Origin" (RTO) patterns. E-commerce and
quick-commerce operations lose real money to delivery agents who mark orders
as `Customer_Unavailable` or `Address_Not_Found` without actually attempting
delivery — the courier's GPS ping at the moment of the failed-status update
sits hundreds of meters to kilometers from the customer's registered address.
This project ingests courier delivery event logs, computes the Haversine
distance between each courier ping and the customer location, flags
distance/dwell-time anomalies on failed-status events, aggregates those
signals into a per-courier risk profile, clusters couriers into risk cohorts
with K-Means, and renders the results in a three-tab Streamlit dashboard so
an ops team can see estimated capital leakage, a leaderboard of couriers
worth auditing, and the underlying geospatial evidence for each flag.

It is built as a portfolio/interview showcase — optimized for clean
architecture and a defensible Polars performance story on a synthetic
dataset with planted ground truth, not for production ingestion of real
operational data.

## Architecture

```
src/rto_audit/
├── config.py       # thresholds (500m / 30s), cost assumptions (₹40-60), k=3, data paths
├── datagen.py       # synthetic delivery_event_logs generator with planted ground-truth profiles
├── geo.py            # vectorized Haversine distance via Polars expressions
├── features.py     # per-event anomaly flags, dwell-time proxy
├── profiling.py    # per-courier aggregation (RTO rate, anomaly count, avg deviation, variance)
├── clustering.py   # StandardScaler + KMeans(k=3) + centroid-to-label mapping
├── pipeline.py      # orchestrates: generate/load -> features -> profile -> cluster
├── store.py          # SQLAlchemy Core schema + save/load of pipeline runs (SQLite or Postgres)
├── s3_source.py      # boto3 S3 client wrapper: upload/list/download event batches (LocalStack or real S3)
└── ingest.py         # composes run_pipeline() + store.save_run() into one persisted run

app/
└── streamlit_app.py  # thin UI: imports rto_audit, renders 3 tabs

scripts/
├── generate_data.py    # CLI: writes a static local CSV (used by the non-Docker "Running locally" path)
├── produce_events.py   # CLI: uploads one synthetic event batch to the S3 bucket
└── ingest_events.py    # CLI: pulls all S3 batches, runs the pipeline, persists the result

tests/                 # pytest suite (config, geo, features, profiling, clustering, pipeline)
Dockerfile             # multi-stage: builder (deps + package) -> slim non-root runtime
docker-compose.yml     # local orchestration: env config, volume, healthcheck, restart policy
.dockerignore
```

Each module in `rto_audit/` has one responsibility and no Streamlit imports,
so the UI could be swapped for a CLI or API later without touching the math.
`pipeline.py` is the single seam both `streamlit_app.py` and any future
entrypoint call through — one source of truth for "raw data → dashboard-ready
result."

### Pipeline flow

1. **`datagen.py`** produces (or `pipeline.py` loads) `delivery_event_logs.csv`
   — one row per courier status-update event, schema: `event_id, courier_id,
   order_id, timestamp, reported_status, courier_latitude, courier_longitude,
   customer_latitude, customer_longitude`.
2. **`geo.py`** adds a `distance_m` column: the Haversine distance between
   the courier's GPS ping and the customer's coordinates for every event.
3. **`features.py`** adds per-event flags: `distance_anomaly` (failed-status
   event with `distance_m > 500`) and `low_dwell_flag` (failed-status event
   where the gap since that courier's previous event is `< 30s`, the proxy
   for "time since arriving in the area").
4. **`profiling.py`** aggregates events to one row per courier: `rto_rate`,
   `anomaly_count`, `avg_deviation_distance` (mean distance on failed
   events), `distance_variance` (spread across *all* events — separates
   couriers with a systemically bad merchant address from couriers who are
   only off-target on failures).
5. **`clustering.py`** scales those four features, runs `KMeans(k=3)`, and
   maps sklearn's arbitrary cluster indices to stable labels by ranking
   centroids on `rto_rate * avg_deviation_distance`: highest →
   `High-Risk/Anomalous`, lowest → `High-Efficiency/Compliant`, remaining →
   `Edge-Case/Requires Audit`.
6. **`app/streamlit_app.py`** renders three tabs: company-wide estimated
   leakage (₹), a leaderboard of the couriers most worth auditing, and a
   geospatial cluster scatter plus a map of the actual flagged GPS pings.

### Results store

`app/streamlit_app.py` no longer recomputes the pipeline on every boot. On
first startup it checks `store.has_any_run()`; if the store is empty it
runs the pipeline once via `ingest.run_and_store()` and persists the result;
every startup after that just reads the latest run via
`store.load_latest_run()`. The schema (`pipeline_runs`, `courier_profiles`,
`events`, `cluster_agreement`) is defined once in `store.py` using
SQLAlchemy Core against whatever `DATABASE_URL` points at — a local SQLite
file by default (resolving to `data/rto_audit.db` under the project root),
or the Postgres service Compose provides (`docker-compose.yml`) when
running containerized. This is the seam a future scheduled ingestion job
plugs into: it will call the same `run_and_store()` on a timer instead of
the UI calling it once on boot.

### Dynamic ingestion (LocalStack S3)

The results store above is one half of the story — the other half is where
events come from. `scripts/produce_events.py` simulates a courier telemetry
feed: it generates a batch of synthetic events and uploads it to an S3
bucket. `scripts/ingest_events.py` picks up every batch currently in that
bucket, concatenates them, and runs the combined events through the same
`run_pipeline()` used everywhere else (via a new optional `events_df`
parameter that lets `run_pipeline()` skip its own generate/load step and
work directly off an already-loaded DataFrame), then persists the result
through the same `store.save_run()` as any other run.

Locally and in Compose, the bucket is emulated with
[LocalStack](https://github.com/localstack/localstack) (free Community
edition, S3 only) rather than a real AWS account — `rto_audit.s3_source`
talks to it through the same boto3 S3 client interface real AWS would use,
so pointing at a real bucket later is a configuration change
(`S3_ENDPOINT_URL`, credentials), not a code change. Tests don't need
LocalStack running at all — they mock S3 in-process with `moto`, the same
"fast in-memory substitute for tests, real service for Compose" split
already used for SQLite vs. Postgres in the results store.

Both scripts are run manually for now (`python scripts/produce_events.py`,
`python scripts/ingest_events.py`) — there's no scheduler wiring them up on
an interval yet; that's separate, later work.

## Why Polars, not Pandas

`geo.py` computes the Haversine distance as native Polars expressions
(`.radians()`, `.sin()`, `.cos()`, `.arcsin()`, `.sqrt()`) evaluated across
the whole DataFrame at once — no `.apply()`, no Python-level row loop. Polars'
query engine executes these expressions in vectorized, multi-threaded Rust
across all ~20,000 events, which is the concrete performance story behind
choosing it over Pandas for this workload: Pandas' `.apply()` path would
fall back to a Python-level loop per row for anything beyond simple
vectorized arithmetic, and even Pandas' vectorized ops run single-threaded.
The rest of the pipeline (`features.py`, `profiling.py`) follows the same
expression-based, no-`.apply()` discipline for the same reason.

## Running locally

```bash
pip install -e ".[dev]"
python scripts/generate_data.py
streamlit run app/streamlit_app.py
```

`scripts/generate_data.py` writes `data/delivery_event_logs.csv` and
`data/ground_truth_profiles.csv` (both gitignored — regenerate anytime).
Optional flags: `--couriers`, `--events`, `--seed` (defaults: 50, 20000, 42).
The Streamlit app no longer regenerates data on every startup — see the
"Results store" section above for how it bootstraps once and then serves
persisted results.

The app persists its results in a local SQLite file (`data/rto_audit.db`
under the project root, gitignored) by default; delete that file if you
want the next startup to regenerate and re-cluster from scratch. Set
`DATABASE_URL` to point at Postgres instead (this is what
`docker-compose.yml` does automatically).

## DevOps

The application layer is the analytics pipeline above; this section is
about how it's packaged, run, and (eventually) deployed and automated.

### Containerization

The `Dockerfile` is a two-stage build, not a single `FROM` with everything
bolted on:

- **`builder`** — installs dependencies from `requirements.txt` into an
  isolated `--prefix=/install`, then builds and installs the `rto_audit`
  package itself (non-editable, `--no-deps`, using the `src`-layout
  discovery already configured in `pyproject.toml`). The dependency-install
  layer is copied/cached separately from the source-install layer, so
  editing application code doesn't force a full dependency re-resolve on
  rebuild.
- **`runtime`** — starts from a fresh `python:3.11-slim`, copies only the
  installed `/install` prefix and the `app/`/`scripts/` directories (no
  `src/`, no pip, no compiler toolchain, no dev dependencies). Runs as a
  non-root `appuser` (UID 1000), not root.

Other choices worth calling out in an interview:

- **No `pytest` in the runtime image.** `requirements.txt` (what the
  Dockerfile installs) intentionally excludes it; `pytest` only comes in
  locally via `pyproject.toml`'s `dev` extra (`pip install -e ".[dev]"`).
  Dev tooling doesn't belong in a production image.
- **`HEALTHCHECK` without adding curl/wget.** The slim base image has no
  HTTP client installed, and adding one just for a healthcheck grows the
  image and the attack surface for no real benefit — the Python
  interpreter that's already there can hit Streamlit's own
  `/_stcore/health` endpoint just as well (`Dockerfile`'s `HEALTHCHECK`
  instruction).
- **`.dockerignore`** keeps `venv/`, `.git/`, `tests/`, `docs/`, and
  generated CSVs out of the build context, so `docker build` isn't
  needlessly slow or leaking unrelated files into layer cache invalidation.

### Local orchestration (Docker Compose)

```bash
docker compose up --build
```

Serves the dashboard at `http://localhost:8501`. What `docker-compose.yml`
actually configures, beyond the minimum to make it start:

- **Ports** — the host port is overridable via `RTO_AUDIT_PORT` (env var or
  `.env` file), defaulting to `8501`; the container always listens on
  `8501` internally, so the two are never accidentally out of sync.
- **Environment** — Streamlit's runtime behavior (`STREAMLIT_SERVER_ADDRESS`,
  `STREAMLIT_SERVER_PORT`, `STREAMLIT_SERVER_HEADLESS`,
  `STREAMLIT_BROWSER_GATHER_USAGE_STATS`) is driven entirely by environment
  variables rather than baked-in CLI flags, so the same image behaves
  correctly under `docker run`, Compose, or (eventually) Kubernetes without
  a rebuild.
- **Volumes** — `./data:/app/data` persists the generated CSVs across
  container restarts and rebuilds instead of regenerating ~20,000 synthetic
  events every time the container starts.
- **Healthcheck** — `docker compose ps` reports `healthy`/`unhealthy` based
  on the same `/_stcore/health` probe as the image's own `HEALTHCHECK`,
  with a 40s `start_period` so the pipeline has time to run once before
  failed probes count against the retry budget.
- **Restart policy** — `unless-stopped`, so a crashed container comes back
  without manual intervention, but an intentional `docker compose stop`
  stays stopped.

### Roadmap: Kubernetes (not yet added)

The image is already built to be orchestrator-agnostic (env-driven config,
a real container healthcheck, no reliance on Compose-specific features),
which is what makes this the natural next step rather than a rewrite.
Planned:

- `Deployment` + `Service` (`ClusterIP` + an `Ingress` or `LoadBalancer` for
  external access) in place of the single Compose service.
- `ConfigMap` for the non-secret `STREAMLIT_*` environment variables
  already defined in `docker-compose.yml`.
- Liveness and readiness probes against `/_stcore/health` — the same
  endpoint the Docker `HEALTHCHECK` already uses, just expressed as k8s
  probes instead of a Docker-level check.
- A `PersistentVolumeClaim` for `/app/data`, replacing the local bind
  mount.
- Resource `requests`/`limits` on the container, since none are set today
  (Compose's `deploy.resources` key is Swarm/Compose-only and isn't in
  `docker-compose.yml` yet either).

### Roadmap: CI/CD (GitHub Actions, not yet added)

No workflow exists in `.github/workflows/` yet. Planned pipeline:

- On every PR: `pytest`, plus a `docker build` (using the `builder` and
  `runtime` targets) to catch Dockerfile regressions before merge.
- On merge to `main`: build and push the `runtime` image to a container
  registry (GHCR), tagged with the commit SHA, so any Kubernetes rollout
  above has something concrete to deploy.
- Dependency drift: a scheduled job re-resolving `requirements.txt` against
  the pinned upper bounds already in place, to catch breaking upstream
  releases (e.g. Plotly/Streamlit deprecations already noted in this repo)
  before they reach a running deployment.

## Running tests

```bash
pytest
```

Covers `geo.py` (distance correctness against hand-computed values),
`features.py` (anomaly/dwell flags on hand-built rows with known expected
output), `profiling.py` (aggregation arithmetic), `clustering.py`
(label-mapping stability against synthetic centroids), `config.py`, and
`pipeline.py` (end-to-end orchestration). `datagen.py` and the Streamlit UI
are not unit tested — generator correctness is evident from the data it
produces, and the UI is verified by running it manually.

## Fact vs. inference — read before acting on this dashboard

The clustering output is a **statistical pattern, not a fraud verdict**.
GPS multipath in dense urban areas and inaccurate merchant/customer
geocoding can both produce large courier-to-customer distances on
completely legitimate deliveries — that is exactly what the
`Edge-Case/Requires Audit` cluster exists to separate out, and even the
`High-Risk/Anomalous` cluster carries a real margin of error (the dashboard
surfaces this as a ~75% confidence signal, i.e. roughly a 25% false-positive
margin). A courier landing on the leaderboard means the pattern in their
telemetry warrants a human audit — it is not, on its own, grounds for
disciplinary or financial action. The UI deliberately avoids the word
"fraudulent" anywhere in courier-facing labels or copy for this reason.
