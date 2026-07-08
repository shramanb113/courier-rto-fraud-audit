from pathlib import Path

DISTANCE_ANOMALY_THRESHOLD_M = 500
LOW_DWELL_THRESHOLD_S = 30

FAILED_STATUSES = ("Customer_Unavailable", "Address_Not_Found")

KMEANS_N_CLUSTERS = 3
KMEANS_RANDOM_STATE = 42

DEFAULT_COST_PER_RTO_INR = 50
COST_PER_RTO_RANGE_INR = (40, 60)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATA_PATH = DATA_DIR / "delivery_event_logs.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth_profiles.csv"
