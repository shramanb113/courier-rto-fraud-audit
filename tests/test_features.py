from datetime import datetime, timedelta

import polars as pl
import pytest

from rto_audit.features import add_features


def _row(status, courier_lat, courier_lon, customer_lat, customer_lon, ts=None, event_id="e1", courier_id="c1", order_id="o1"):
    return {
        "event_id": event_id,
        "courier_id": courier_id,
        "order_id": order_id,
        "timestamp": ts or datetime(2026, 1, 1, 10, 0, 0),
        "reported_status": status,
        "courier_latitude": courier_lat,
        "courier_longitude": courier_lon,
        "customer_latitude": customer_lat,
        "customer_longitude": customer_lon,
    }


def test_distance_anomaly_flagged_for_failed_status_beyond_threshold():
    df = pl.DataFrame([_row("Customer_Unavailable", 12.9716, 77.5946, 13.1986, 77.7066)])
    result = add_features(df)
    assert result["distance_anomaly"][0] == 1


def test_distance_anomaly_not_flagged_for_delivered_status_even_if_far():
    df = pl.DataFrame([_row("Delivered", 12.9716, 77.5946, 13.1986, 77.7066)])
    result = add_features(df)
    assert result["distance_anomaly"][0] == 0


def test_distance_anomaly_not_flagged_within_threshold():
    df = pl.DataFrame([_row("Customer_Unavailable", 12.9716, 77.5946, 12.9718, 77.5946)])
    result = add_features(df)
    assert result["distance_anomaly"][0] == 0


def test_low_dwell_flag_for_quick_failed_update_after_previous_event():
    base = datetime(2026, 1, 1, 10, 0, 0)
    df = pl.DataFrame(
        [
            _row("Delivered", 12.9716, 77.5946, 12.9716, 77.5946, ts=base, event_id="e1", order_id="o1"),
            _row(
                "Customer_Unavailable",
                12.9716,
                77.5946,
                12.9716,
                77.5946,
                ts=base + timedelta(seconds=10),
                event_id="e2",
                order_id="o2",
            ),
        ]
    )
    result = add_features(df)
    second = result.filter(pl.col("event_id") == "e2")
    assert second["dwell_seconds"][0] == pytest.approx(10.0)
    assert second["low_dwell_flag"][0] == 1


def test_low_dwell_flag_false_for_first_event_per_courier():
    df = pl.DataFrame([_row("Customer_Unavailable", 12.9716, 77.5946, 12.9716, 77.5946)])
    result = add_features(df)
    assert result["dwell_seconds"][0] is None
    assert result["low_dwell_flag"][0] == 0
