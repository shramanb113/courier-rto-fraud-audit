import pytest
from moto import mock_aws
from sqlalchemy import create_engine

from rto_audit.datagen import generate_delivery_logs
from rto_audit.ingest import run_and_store, run_and_store_from_s3
from rto_audit.s3_source import ensure_bucket, get_s3_client, upload_batch
from rto_audit.store import has_any_run, init_schema, load_latest_run


def test_run_and_store_persists_a_queryable_run():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_schema(engine)

    run_id = run_and_store(engine, regenerate=True, n_couriers=12, n_events=600, seed=7)

    assert isinstance(run_id, int)
    assert has_any_run(engine) is True

    loaded = load_latest_run(engine)
    assert loaded is not None
    assert loaded.clustered_df.height == 12
    assert "cluster_label" in loaded.clustered_df.columns


@mock_aws
def test_run_and_store_from_s3_ingests_uploaded_batch():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_schema(engine)

    s3_client = get_s3_client()
    ensure_bucket(s3_client, "test-bucket")

    events_df, _ = generate_delivery_logs(n_couriers=5, n_events=100, seed=11)
    upload_batch(s3_client, "test-bucket", events_df)

    run_id = run_and_store_from_s3(engine, s3_client, "test-bucket")

    assert isinstance(run_id, int)
    loaded = load_latest_run(engine)
    assert loaded.clustered_df.height == 5


@mock_aws
def test_run_and_store_from_s3_combines_multiple_batches():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_schema(engine)

    s3_client = get_s3_client()
    ensure_bucket(s3_client, "multi-bucket")

    batch1, _ = generate_delivery_logs(n_couriers=3, n_events=60, seed=1)
    batch2, _ = generate_delivery_logs(n_couriers=3, n_events=60, seed=2)
    upload_batch(s3_client, "multi-bucket", batch1)
    upload_batch(s3_client, "multi-bucket", batch2)

    run_and_store_from_s3(engine, s3_client, "multi-bucket")

    loaded = load_latest_run(engine)
    assert loaded.clustered_df.height == 3
    assert loaded.events_df.height == batch1.height + batch2.height


@mock_aws
def test_run_and_store_from_s3_raises_when_bucket_has_no_batches():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_schema(engine)

    s3_client = get_s3_client()
    ensure_bucket(s3_client, "empty-bucket")

    with pytest.raises(ValueError):
        run_and_store_from_s3(engine, s3_client, "empty-bucket")
