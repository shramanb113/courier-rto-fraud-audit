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
└── pipeline.py      # orchestrates: generate/load -> features -> profile -> cluster

app/
└── streamlit_app.py  # thin UI: imports rto_audit, renders 3 tabs

scripts/
└── generate_data.py  # CLI: python scripts/generate_data.py --couriers 50 --events 20000 --seed 42

tests/                 # pytest suite (config, geo, features, profiling, clustering, pipeline)
Dockerfile
docker-compose.yml
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
The Streamlit app itself calls `run_pipeline(regenerate=True, ...)` on
startup, so it always demos against a freshly generated, reproducible
dataset (seeded) even if you skip the manual generation step.

## Running via Docker

```bash
docker compose up --build
```

Serves the dashboard at `http://localhost:8501`. `data/` is mounted as a
volume so regenerating data doesn't require a rebuild.

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
