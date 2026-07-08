import math

import polars as pl
import pytest

from rto_audit.geo import add_distance_column


def _reference_haversine(lat1, lon1, lat2, lon2):
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@pytest.mark.parametrize(
    "lat1,lon1,lat2,lon2",
    [
        (12.9716, 77.5946, 12.9716, 77.5946),  # identical point -> 0
        (0.0, 0.0, 1.0, 0.0),  # 1 degree of latitude
        (12.9716, 77.5946, 13.1986, 77.7066),  # Bengaluru city -> airport, ~35km
        (28.6139, 77.2090, 19.0760, 72.8777),  # Delhi -> Mumbai, ~1150km
    ],
)
def test_matches_reference_haversine(lat1, lon1, lat2, lon2):
    df = pl.DataFrame(
        {
            "courier_latitude": [lat1],
            "courier_longitude": [lon1],
            "customer_latitude": [lat2],
            "customer_longitude": [lon2],
        }
    )
    result = add_distance_column(df)
    expected = _reference_haversine(lat1, lon1, lat2, lon2)
    assert result["distance_m"][0] == pytest.approx(expected, rel=1e-6, abs=1e-6)


def test_preserves_existing_columns():
    df = pl.DataFrame(
        {
            "event_id": ["e1"],
            "courier_latitude": [12.9716],
            "courier_longitude": [77.5946],
            "customer_latitude": [12.9716],
            "customer_longitude": [77.5946],
        }
    )
    result = add_distance_column(df)
    assert "event_id" in result.columns
    assert "distance_m" in result.columns
