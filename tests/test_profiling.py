import statistics

import polars as pl
import pytest

from rto_audit.profiling import profile_couriers


def test_aggregates_rto_rate_and_anomaly_count_per_courier():
    df = pl.DataFrame(
        {
            "courier_id": ["c1", "c1", "c1", "c2"],
            "reported_status": ["Delivered", "Customer_Unavailable", "Customer_Unavailable", "Delivered"],
            "distance_m": [50.0, 600.0, 700.0, 40.0],
            "distance_anomaly": [0, 1, 1, 0],
        }
    )
    result = profile_couriers(df)

    c1 = result.filter(pl.col("courier_id") == "c1")
    assert c1["total_events"][0] == 3
    assert c1["failed_status_count"][0] == 2
    assert c1["rto_rate"][0] == pytest.approx(2 / 3)
    assert c1["anomaly_count"][0] == 2
    assert c1["avg_deviation_distance"][0] == pytest.approx(650.0)
    assert c1["distance_variance"][0] == pytest.approx(statistics.stdev([50.0, 600.0, 700.0]))

    c2 = result.filter(pl.col("courier_id") == "c2")
    assert c2["total_events"][0] == 1
    assert c2["rto_rate"][0] == pytest.approx(0.0)
    assert c2["avg_deviation_distance"][0] == pytest.approx(0.0)
    assert c2["distance_variance"][0] == pytest.approx(0.0)
