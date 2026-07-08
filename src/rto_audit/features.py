import polars as pl

from rto_audit.config import DISTANCE_ANOMALY_THRESHOLD_M, FAILED_STATUSES, LOW_DWELL_THRESHOLD_S
from rto_audit.geo import add_distance_column


def add_features(df: pl.DataFrame) -> pl.DataFrame:
    df = add_distance_column(df)
    df = df.sort(["courier_id", "timestamp"])
    df = df.with_columns(
        pl.col("timestamp").diff().over("courier_id").dt.total_seconds().alias("dwell_seconds")
    )

    is_failed = pl.col("reported_status").is_in(list(FAILED_STATUSES))

    distance_anomaly = (is_failed & (pl.col("distance_m") > DISTANCE_ANOMALY_THRESHOLD_M)).cast(
        pl.Int8
    )
    low_dwell_flag = (
        (is_failed & (pl.col("dwell_seconds") < LOW_DWELL_THRESHOLD_S)).fill_null(False).cast(pl.Int8)
    )

    return df.with_columns(
        [
            distance_anomaly.alias("distance_anomaly"),
            low_dwell_flag.alias("low_dwell_flag"),
        ]
    )
