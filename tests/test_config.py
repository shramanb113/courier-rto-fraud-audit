from rto_audit import config


def test_thresholds_have_expected_values():
    assert config.DISTANCE_ANOMALY_THRESHOLD_M == 500
    assert config.LOW_DWELL_THRESHOLD_S == 30
    assert config.KMEANS_N_CLUSTERS == 3
    assert config.KMEANS_RANDOM_STATE == 42
    assert config.FAILED_STATUSES == ("Customer_Unavailable", "Address_Not_Found")


def test_cost_range_is_sane():
    low, high = config.COST_PER_RTO_RANGE_INR
    assert low < config.DEFAULT_COST_PER_RTO_INR < high


def test_data_paths_are_under_data_dir():
    assert config.DEFAULT_DATA_PATH.parent == config.DATA_DIR
    assert config.DATA_DIR.name == "data"
