from dataclasses import dataclass
from pathlib import Path

import polars as pl

from rto_audit.clustering import cluster_couriers, validate_cluster_agreement
from rto_audit.config import DEFAULT_DATA_PATH, GROUND_TRUTH_PATH
from rto_audit.datagen import generate_delivery_logs
from rto_audit.features import add_features
from rto_audit.profiling import profile_couriers


@dataclass
class PipelineResult:
    events_df: pl.DataFrame
    profile_df: pl.DataFrame
    clustered_df: pl.DataFrame
    agreement_df: pl.DataFrame | None


def run_pipeline(
    data_path: Path | None = None,
    regenerate: bool = False,
    n_couriers: int = 50,
    n_events: int = 20_000,
    seed: int = 42,
    events_df: pl.DataFrame | None = None,
) -> PipelineResult:
    ground_truth_df = None

    if events_df is not None:
        pass
    elif regenerate or (data_path is None and not DEFAULT_DATA_PATH.exists()):
        events_df, ground_truth_df = generate_delivery_logs(
            n_couriers=n_couriers, n_events=n_events, seed=seed
        )
    else:
        path = data_path or DEFAULT_DATA_PATH
        events_df = pl.read_csv(path, try_parse_dates=True)
        if GROUND_TRUTH_PATH.exists():
            ground_truth_df = pl.read_csv(GROUND_TRUTH_PATH)

    featured_df = add_features(events_df)
    profile_df = profile_couriers(featured_df)
    clustered_df = cluster_couriers(profile_df)

    agreement_df = None
    if ground_truth_df is not None:
        agreement_df = validate_cluster_agreement(clustered_df, ground_truth_df)

    return PipelineResult(
        events_df=featured_df,
        profile_df=profile_df,
        clustered_df=clustered_df,
        agreement_df=agreement_df,
    )
