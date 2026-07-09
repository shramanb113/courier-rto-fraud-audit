from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)

from rto_audit.pipeline import PipelineResult

metadata = MetaData()

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("run_id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime, nullable=False),
    Column("n_events", Integer, nullable=False),
    Column("n_couriers", Integer, nullable=False),
)

courier_profiles = Table(
    "courier_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, nullable=False),
    Column("courier_id", String, nullable=False),
    Column("total_events", Integer, nullable=False),
    Column("failed_status_count", Integer, nullable=False),
    Column("avg_deviation_distance", Float, nullable=False),
    Column("distance_variance", Float, nullable=False),
    Column("anomaly_count", Integer, nullable=False),
    Column("rto_rate", Float, nullable=False),
    Column("cluster_label", String, nullable=False),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, nullable=False),
    Column("event_id", String, nullable=False),
    Column("courier_id", String, nullable=False),
    Column("timestamp", DateTime, nullable=False),
    Column("reported_status", String, nullable=False),
    Column("courier_latitude", Float, nullable=False),
    Column("courier_longitude", Float, nullable=False),
    Column("customer_latitude", Float, nullable=False),
    Column("customer_longitude", Float, nullable=False),
    Column("distance_m", Float, nullable=False),
    Column("distance_anomaly", Integer, nullable=False),
)

cluster_agreement = Table(
    "cluster_agreement",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, nullable=False),
    Column("planted_profile", String, nullable=False),
    Column("cluster_label", String, nullable=False),
    Column("count", Integer, nullable=False),
)

PROFILE_SCHEMA = {
    "courier_id": pl.Utf8,
    "total_events": pl.Int64,
    "failed_status_count": pl.Int64,
    "avg_deviation_distance": pl.Float64,
    "distance_variance": pl.Float64,
    "anomaly_count": pl.Int64,
    "rto_rate": pl.Float64,
    "cluster_label": pl.Utf8,
}
PROFILE_COLUMNS = list(PROFILE_SCHEMA)

# Persisted event schema is a deliberate UI-facing subset of run_pipeline()'s
# full events_df: dwell_seconds and low_dwell_flag are dropped (unused by
# streamlit_app.py), and distance_anomaly is stored/reloaded as Int64 rather
# than run_pipeline()'s Int8. A store-loaded PipelineResult.events_df is not
# byte-for-byte identical to a live run's.
EVENT_SCHEMA = {
    "event_id": pl.Utf8,
    "courier_id": pl.Utf8,
    "timestamp": pl.Datetime,
    "reported_status": pl.Utf8,
    "courier_latitude": pl.Float64,
    "courier_longitude": pl.Float64,
    "customer_latitude": pl.Float64,
    "customer_longitude": pl.Float64,
    "distance_m": pl.Float64,
    "distance_anomaly": pl.Int64,
}
EVENT_COLUMNS = list(EVENT_SCHEMA)

AGREEMENT_SCHEMA = {
    "planted_profile": pl.Utf8,
    "cluster_label": pl.Utf8,
    "count": pl.Int64,
}
AGREEMENT_COLUMNS = list(AGREEMENT_SCHEMA)


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def init_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def has_any_run(engine: Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(select(pipeline_runs.c.run_id).limit(1)).first()
    return row is not None


def save_run(engine: Engine, result: PipelineResult) -> int:
    with engine.begin() as conn:
        run_id = conn.execute(
            insert(pipeline_runs).values(
                created_at=datetime.now(timezone.utc),
                n_events=result.events_df.height,
                n_couriers=result.profile_df.height,
            )
        ).inserted_primary_key[0]

        profile_rows = result.clustered_df.select(PROFILE_COLUMNS).to_dicts()
        for row in profile_rows:
            row["run_id"] = run_id
        if profile_rows:
            conn.execute(insert(courier_profiles), profile_rows)

        event_rows = result.events_df.select(EVENT_COLUMNS).to_dicts()
        for row in event_rows:
            row["run_id"] = run_id
        if event_rows:
            conn.execute(insert(events), event_rows)

        if result.agreement_df is not None:
            agreement_rows = result.agreement_df.select(AGREEMENT_COLUMNS).to_dicts()
            for row in agreement_rows:
                row["run_id"] = run_id
            if agreement_rows:
                conn.execute(insert(cluster_agreement), agreement_rows)

    return run_id


def _rows_to_df(rows: list[dict], schema: dict) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame([dict(row) for row in rows], schema=schema)


def get_latest_run_id(engine: Engine) -> int | None:
    with engine.connect() as conn:
        return conn.execute(
            select(pipeline_runs.c.run_id).order_by(pipeline_runs.c.run_id.desc()).limit(1)
        ).scalar()


def load_latest_run(engine: Engine) -> PipelineResult | None:
    latest_run_id = get_latest_run_id(engine)
    if latest_run_id is None:
        return None

    with engine.connect() as conn:
        profile_rows = conn.execute(
            select(*[courier_profiles.c[name] for name in PROFILE_COLUMNS]).where(
                courier_profiles.c.run_id == latest_run_id
            )
        ).mappings().all()
        event_rows = conn.execute(
            select(*[events.c[name] for name in EVENT_COLUMNS]).where(
                events.c.run_id == latest_run_id
            )
        ).mappings().all()
        agreement_rows = conn.execute(
            select(*[cluster_agreement.c[name] for name in AGREEMENT_COLUMNS]).where(
                cluster_agreement.c.run_id == latest_run_id
            )
        ).mappings().all()

    clustered_df = _rows_to_df(profile_rows, PROFILE_SCHEMA)
    events_df = _rows_to_df(event_rows, EVENT_SCHEMA)
    agreement_df = _rows_to_df(agreement_rows, AGREEMENT_SCHEMA) if agreement_rows else None

    return PipelineResult(
        events_df=events_df,
        profile_df=clustered_df.drop("cluster_label"),
        clustered_df=clustered_df,
        agreement_df=agreement_df,
    )
