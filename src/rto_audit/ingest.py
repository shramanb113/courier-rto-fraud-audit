from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine

from rto_audit.pipeline import run_pipeline
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
