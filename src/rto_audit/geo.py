import polars as pl

EARTH_RADIUS_M = 6_371_000


def _haversine_expr(lat1: str, lon1: str, lat2: str, lon2: str) -> pl.Expr:
    lat1_rad = pl.col(lat1).radians()
    lat2_rad = pl.col(lat2).radians()
    dlat = (pl.col(lat2) - pl.col(lat1)).radians()
    dlon = (pl.col(lon2) - pl.col(lon1)).radians()

    a = (dlat / 2).sin().pow(2) + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2).sin().pow(2)
    c = 2 * a.sqrt().arcsin()
    return (EARTH_RADIUS_M * c).alias("distance_m")


def add_distance_column(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        _haversine_expr(
            "courier_latitude", "courier_longitude", "customer_latitude", "customer_longitude"
        )
    )
