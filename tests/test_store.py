from datetime import datetime

import polars as pl
import pytest
from sqlalchemy import create_engine

from rto_audit.pipeline import PipelineResult
from rto_audit.store import has_any_run, init_schema, load_latest_run, save_run


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    init_schema(eng)
    return eng


def _make_result(courier_prefix: str = "c") -> PipelineResult:
    clustered_df = pl.DataFrame(
        {
            "courier_id": [f"{courier_prefix}1", f"{courier_prefix}2"],
            "total_events": [10, 5],
            "failed_status_count": [2, 1],
            "avg_deviation_distance": [650.0, 40.0],
            "distance_variance": [120.0, 15.0],
            "anomaly_count": [2, 0],
            "rto_rate": [0.2, 0.2],
            "cluster_label": ["High-Risk/Anomalous", "High-Efficiency/Compliant"],
        }
    )
    events_df = pl.DataFrame(
        {
            "event_id": ["e1"],
            "courier_id": [f"{courier_prefix}1"],
            "timestamp": [datetime(2026, 6, 1, 9, 0, 0)],
            "reported_status": ["Customer_Unavailable"],
            "courier_latitude": [19.0],
            "courier_longitude": [72.9],
            "customer_latitude": [19.01],
            "customer_longitude": [72.91],
            "distance_m": [650.0],
            "distance_anomaly": [1],
        }
    )
    agreement_df = pl.DataFrame(
        {
            "planted_profile": ["fraudulent"],
            "cluster_label": ["High-Risk/Anomalous"],
            "count": [1],
        }
    )
    return PipelineResult(
        events_df=events_df,
        profile_df=clustered_df.drop("cluster_label"),
        clustered_df=clustered_df,
        agreement_df=agreement_df,
    )


def test_has_any_run_false_on_empty_store(engine):
    assert has_any_run(engine) is False


def test_load_latest_run_returns_none_when_store_empty(engine):
    assert load_latest_run(engine) is None


def test_save_and_load_latest_run_round_trips_profiles_events_and_agreement(engine):
    run_id = save_run(engine, _make_result())

    assert isinstance(run_id, int)
    assert has_any_run(engine) is True

    loaded = load_latest_run(engine)
    assert loaded is not None
    assert sorted(loaded.clustered_df["courier_id"].to_list()) == ["c1", "c2"]
    assert loaded.events_df.height == 1
    assert loaded.events_df["event_id"][0] == "e1"
    assert loaded.agreement_df is not None
    assert loaded.agreement_df["count"][0] == 1


def test_save_run_twice_load_latest_returns_most_recent(engine):
    first_run_id = save_run(engine, _make_result(courier_prefix="c"))
    second_run_id = save_run(engine, _make_result(courier_prefix="z"))

    assert second_run_id > first_run_id

    loaded = load_latest_run(engine)
    assert sorted(loaded.clustered_df["courier_id"].to_list()) == ["z1", "z2"]
