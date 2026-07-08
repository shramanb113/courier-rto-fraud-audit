import polars as pl

from rto_audit.config import FAILED_STATUSES


def profile_couriers(df: pl.DataFrame) -> pl.DataFrame:
    is_failed = pl.col("reported_status").is_in(list(FAILED_STATUSES))

    profile = (
        df.group_by("courier_id")
        .agg(
            [
                pl.len().alias("total_events"),
                is_failed.sum().alias("failed_status_count"),
                pl.col("distance_m").filter(is_failed).mean().fill_null(0.0).alias(
                    "avg_deviation_distance"
                ),
                pl.col("distance_m").std().fill_null(0.0).alias("distance_variance"),
                pl.col("distance_anomaly").sum().alias("anomaly_count"),
            ]
        )
        .with_columns((pl.col("failed_status_count") / pl.col("total_events")).alias("rto_rate"))
        .sort("courier_id")
    )
    return profile
