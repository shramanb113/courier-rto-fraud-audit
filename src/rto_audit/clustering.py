import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from rto_audit.config import KMEANS_N_CLUSTERS, KMEANS_RANDOM_STATE

CLUSTER_FEATURES = ["rto_rate", "anomaly_count", "avg_deviation_distance", "distance_variance"]

LABEL_HIGH_RISK = "High-Risk/Anomalous"
LABEL_COMPLIANT = "High-Efficiency/Compliant"
LABEL_EDGE_CASE = "Edge-Case/Requires Audit"


def _label_centroids(centroids: np.ndarray, feature_names: list[str]) -> dict[int, str]:
    rto_idx = feature_names.index("rto_rate")
    dist_idx = feature_names.index("avg_deviation_distance")

    risk_score = centroids[:, rto_idx] * centroids[:, dist_idx]
    high_risk_cluster = int(np.argmax(risk_score))

    remaining = [i for i in range(len(centroids)) if i != high_risk_cluster]
    compliant_cluster = min(remaining, key=lambda i: risk_score[i])
    edge_case_cluster = next(i for i in remaining if i != compliant_cluster)

    return {
        high_risk_cluster: LABEL_HIGH_RISK,
        compliant_cluster: LABEL_COMPLIANT,
        edge_case_cluster: LABEL_EDGE_CASE,
    }


def cluster_couriers(profile_df: pl.DataFrame) -> pl.DataFrame:
    feature_matrix = profile_df.select(CLUSTER_FEATURES).to_numpy()

    scaler = StandardScaler()
    scaled = scaler.fit_transform(feature_matrix)

    kmeans = KMeans(n_clusters=KMEANS_N_CLUSTERS, random_state=KMEANS_RANDOM_STATE, n_init=10)
    cluster_ids = kmeans.fit_predict(scaled)

    unscaled_centroids = scaler.inverse_transform(kmeans.cluster_centers_)
    label_map = _label_centroids(unscaled_centroids, CLUSTER_FEATURES)

    labels = [label_map[cluster_id] for cluster_id in cluster_ids]
    return profile_df.with_columns(pl.Series("cluster_label", labels))


def validate_cluster_agreement(clustered_df: pl.DataFrame, ground_truth_df: pl.DataFrame) -> pl.DataFrame:
    joined = clustered_df.join(ground_truth_df, on="courier_id")
    return (
        joined.group_by(["planted_profile", "cluster_label"])
        .agg(pl.len().alias("count"))
        .sort(["planted_profile", "cluster_label"])
    )
