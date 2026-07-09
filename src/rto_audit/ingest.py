from __future__ import annotations

from pathlib import Path

import polars as pl
from sqlalchemy import Engine

from rto_audit.pipeline import run_pipeline
from rto_audit.s3_source import download_batch, list_batch_keys
from rto_audit.store import save_run


def run_and_store(
    engine: Engine,
    data_path: Path | None = None,
    regenerate: bool = False,
    n_couriers: int = 50,
    n_events: int = 20_000,
    seed: int = 42,
) -> int:
    result = run_pipeline(
        data_path=data_path,
        regenerate=regenerate,
        n_couriers=n_couriers,
        n_events=n_events,
        seed=seed,
    )
    return save_run(engine, result)


def run_and_store_from_s3(engine: Engine, s3_client, bucket: str) -> int:
    keys = list_batch_keys(s3_client, bucket)
    if not keys:
        raise ValueError(f"no event batches found in bucket '{bucket}'")

    batches = [download_batch(s3_client, bucket, key) for key in keys]
    events_df = pl.concat(batches)

    result = run_pipeline(events_df=events_df)
    return save_run(engine, result)
