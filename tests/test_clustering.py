import numpy as np
import polars as pl
import pytest

from rto_audit.clustering import (
    CLUSTER_FEATURES,
    LABEL_COMPLIANT,
    LABEL_EDGE_CASE,
    LABEL_HIGH_RISK,
    _label_centroids,
    cluster_couriers,
    validate_cluster_agreement,
)


def test_label_centroids_identifies_high_risk_compliant_and_edge_case():
    # columns match CLUSTER_FEATURES order: rto_rate, anomaly_count, avg_deviation_distance, distance_variance
    centroids = np.array(
        [
            [0.06, 1.0, 80.0, 60.0],  # compliant: low everything
            [0.30, 8.0, 900.0, 150.0],  # high-risk: high rto + high distance
            [0.08, 1.5, 100.0, 500.0],  # edge-case: low rto, very high variance
        ]
    )
    labels = _label_centroids(centroids, CLUSTER_FEATURES)
    assert labels[0] == LABEL_COMPLIANT
    assert labels[1] == LABEL_HIGH_RISK
    assert labels[2] == LABEL_EDGE_CASE


def test_cluster_couriers_end_to_end_assigns_all_three_labels():
    rng = np.random.default_rng(42)

    def _make_group(prefix, rto_mean, anomaly_mean, dist_mean, var_mean, n=10):
        return {
            "courier_id": [f"{prefix}{i}" for i in range(n)],
            "rto_rate": rng.normal(rto_mean, rto_mean * 0.1, n).tolist(),
            "anomaly_count": rng.normal(anomaly_mean, anomaly_mean * 0.1 + 0.1, n).tolist(),
            "avg_deviation_distance": rng.normal(dist_mean, dist_mean * 0.1, n).tolist(),
            "distance_variance": rng.normal(var_mean, var_mean * 0.1, n).tolist(),
        }

    df = pl.concat(
        [
            pl.DataFrame(_make_group("compliant_", 0.06, 1, 80, 60)),
            pl.DataFrame(_make_group("risky_", 0.30, 8, 900, 150)),
            pl.DataFrame(_make_group("edge_", 0.08, 1.5, 100, 500)),
        ]
    )
    result = cluster_couriers(df)

    def label_for(prefix):
        rows = result.filter(pl.col("courier_id").str.starts_with(prefix))
        return set(rows["cluster_label"].to_list())

    assert label_for("compliant_") == {LABEL_COMPLIANT}
    assert label_for("risky_") == {LABEL_HIGH_RISK}
    assert label_for("edge_") == {LABEL_EDGE_CASE}


def test_validate_cluster_agreement_crosstab_counts():
    clustered = pl.DataFrame(
        {
            "courier_id": ["a", "b", "c", "d"],
            "cluster_label": [LABEL_COMPLIANT, LABEL_COMPLIANT, LABEL_HIGH_RISK, LABEL_EDGE_CASE],
        }
    )
    ground_truth = pl.DataFrame(
        {
            "courier_id": ["a", "b", "c", "d"],
            "planted_profile": ["compliant", "compliant", "fraudulent", "edge_case"],
        }
    )
    result = validate_cluster_agreement(clustered, ground_truth)
    row = result.filter(
        (pl.col("planted_profile") == "compliant") & (pl.col("cluster_label") == LABEL_COMPLIANT)
    )
    assert row["count"][0] == 2
