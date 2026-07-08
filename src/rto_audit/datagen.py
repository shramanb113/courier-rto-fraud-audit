import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import polars as pl

STATUSES_FAILED = ["Customer_Unavailable", "Address_Not_Found", "Refused_by_Customer"]

METRO_BOUNDING_BOXES = {
    "mumbai": (18.90, 19.25, 72.80, 73.00),
    "delhi_ncr": (28.40, 28.80, 76.90, 77.35),
    "bengaluru": (12.85, 13.10, 77.50, 77.75),
}

PROFILE_SHARES = {"compliant": 0.70, "fraudulent": 0.15, "edge_case": 0.15}

PROFILE_PARAMS = {
    "compliant": {"failed_rate": (0.05, 0.08), "normal_drift_m": (50, 150), "fraud_drift_m": None},
    "fraudulent": {"failed_rate": (0.25, 0.35), "normal_drift_m": (50, 150), "fraud_drift_m": (500, 3000)},
    "edge_case": {"failed_rate": (0.05, 0.08), "normal_drift_m": (200, 800), "fraud_drift_m": None},
}


@dataclass
class Courier:
    courier_id: str
    profile: str
    metro: str
    failed_rate: float


def _assign_courier_profiles(n_couriers: int, rng: np.random.Generator) -> list[Courier]:
    profiles = (
        ["compliant"] * round(n_couriers * PROFILE_SHARES["compliant"])
        + ["fraudulent"] * round(n_couriers * PROFILE_SHARES["fraudulent"])
        + ["edge_case"] * round(n_couriers * PROFILE_SHARES["edge_case"])
    )
    while len(profiles) < n_couriers:
        profiles.append("compliant")
    profiles = profiles[:n_couriers]
    rng.shuffle(profiles)

    metros = list(METRO_BOUNDING_BOXES)
    couriers = []
    for i, profile in enumerate(profiles):
        low, high = PROFILE_PARAMS[profile]["failed_rate"]
        couriers.append(
            Courier(
                courier_id=f"COUR{i:04d}",
                profile=profile,
                metro=metros[i % len(metros)],
                failed_rate=float(rng.uniform(low, high)),
            )
        )
    return couriers


def _random_point_in_box(box, rng: np.random.Generator) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = box
    return float(rng.uniform(lat_min, lat_max)), float(rng.uniform(lon_min, lon_max))


def _offset_point_by_meters(lat: float, lon: float, meters: float, rng: np.random.Generator) -> tuple[float, float]:
    angle = rng.uniform(0, 2 * np.pi)
    d_lat = (meters * np.cos(angle)) / 111_320
    d_lon = (meters * np.sin(angle)) / (111_320 * np.cos(np.radians(lat)))
    return lat + d_lat, lon + d_lon


def _generate_events_for_courier(courier: Courier, n_orders: int, rng: np.random.Generator) -> list[dict]:
    box = METRO_BOUNDING_BOXES[courier.metro]
    params = PROFILE_PARAMS[courier.profile]
    day_start = datetime(2026, 6, 1, 9, 0, 0)

    events = []
    for order_idx in range(n_orders):
        customer_lat, customer_lon = _random_point_in_box(box, rng)
        is_failed = rng.random() < courier.failed_rate
        status = str(rng.choice(STATUSES_FAILED)) if is_failed else "Delivered"

        use_fraud_drift = is_failed and params["fraud_drift_m"] is not None and rng.random() < 0.6
        drift_range = params["fraud_drift_m"] if use_fraud_drift else params["normal_drift_m"]
        drift_m = rng.uniform(*drift_range)
        courier_lat, courier_lon = _offset_point_by_meters(customer_lat, customer_lon, drift_m, rng)

        minutes_offset = int(order_idx * (660 / max(n_orders, 1)) + rng.uniform(-5, 5))
        timestamp = day_start + timedelta(minutes=max(0, minutes_offset))

        events.append(
            {
                "event_id": str(uuid.uuid4()),
                "courier_id": courier.courier_id,
                "order_id": f"{courier.courier_id}-ORD{order_idx:04d}",
                "timestamp": timestamp,
                "reported_status": status,
                "courier_latitude": courier_lat,
                "courier_longitude": courier_lon,
                "customer_latitude": customer_lat,
                "customer_longitude": customer_lon,
            }
        )
    return events


def generate_delivery_logs(
    n_couriers: int = 50, n_events: int = 20_000, seed: int = 42
) -> tuple[pl.DataFrame, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    couriers = _assign_courier_profiles(n_couriers, rng)
    orders_per_courier = max(1, n_events // n_couriers)

    all_events = []
    for courier in couriers:
        all_events.extend(_generate_events_for_courier(courier, orders_per_courier, rng))

    events_df = pl.DataFrame(all_events).sort(["courier_id", "timestamp"])
    ground_truth_df = pl.DataFrame(
        {
            "courier_id": [c.courier_id for c in couriers],
            "planted_profile": [c.profile for c in couriers],
        }
    )
    return events_df, ground_truth_df
