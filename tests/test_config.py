import importlib

from rto_audit import config


def test_database_url_defaults_to_sqlite_under_data_dir(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(config)
    assert config.DATABASE_URL == f"sqlite:///{config.DATA_DIR / 'rto_audit.db'}"


def test_database_url_honors_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@host:5432/db")
    try:
        importlib.reload(config)
        assert config.DATABASE_URL == "postgresql+psycopg2://u:p@host:5432/db"
    finally:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(config)


def test_s3_endpoint_url_defaults_to_localstack(monkeypatch):
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    importlib.reload(config)
    assert config.S3_ENDPOINT_URL == "http://localhost:4566"


def test_s3_endpoint_url_honors_env_override(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localstack:4566")
    try:
        importlib.reload(config)
        assert config.S3_ENDPOINT_URL == "http://localstack:4566"
    finally:
        monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
        importlib.reload(config)


def test_s3_bucket_name_defaults_to_rto_audit_events(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    importlib.reload(config)
    assert config.S3_BUCKET_NAME == "rto-audit-events"


def test_s3_bucket_name_honors_env_override(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "custom-bucket")
    try:
        importlib.reload(config)
        assert config.S3_BUCKET_NAME == "custom-bucket"
    finally:
        monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
        importlib.reload(config)


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
