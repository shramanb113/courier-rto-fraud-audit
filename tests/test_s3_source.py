import polars as pl
from moto import mock_aws

from rto_audit.s3_source import (
    download_batch,
    ensure_bucket,
    get_s3_client,
    list_batch_keys,
    upload_batch,
)

BUCKET = "rto-audit-events-test"


@mock_aws
def test_ensure_bucket_creates_bucket_when_missing():
    client = get_s3_client()
    ensure_bucket(client, BUCKET)

    buckets = client.list_buckets()["Buckets"]
    assert any(b["Name"] == BUCKET for b in buckets)


@mock_aws
def test_ensure_bucket_is_idempotent():
    client = get_s3_client()
    ensure_bucket(client, BUCKET)
    ensure_bucket(client, BUCKET)

    buckets = client.list_buckets()["Buckets"]
    assert sum(1 for b in buckets if b["Name"] == BUCKET) == 1


@mock_aws
def test_upload_and_download_batch_round_trips_events():
    client = get_s3_client()
    ensure_bucket(client, BUCKET)

    events_df = pl.DataFrame(
        {
            "event_id": ["e1", "e2"],
            "courier_id": ["c1", "c1"],
            "distance_m": [10.0, 650.0],
        }
    )
    key = upload_batch(client, BUCKET, events_df)

    downloaded = download_batch(client, BUCKET, key)
    assert downloaded.height == 2
    assert sorted(downloaded["event_id"].to_list()) == ["e1", "e2"]


@mock_aws
def test_list_batch_keys_returns_all_uploaded_batches_sorted():
    client = get_s3_client()
    ensure_bucket(client, BUCKET)

    df = pl.DataFrame({"event_id": ["e1"], "courier_id": ["c1"], "distance_m": [10.0]})
    key1 = upload_batch(client, BUCKET, df)
    key2 = upload_batch(client, BUCKET, df)

    keys = list_batch_keys(client, BUCKET)
    assert keys == sorted([key1, key2])


@mock_aws
def test_list_batch_keys_empty_bucket_returns_empty_list():
    client = get_s3_client()
    ensure_bucket(client, BUCKET)

    assert list_batch_keys(client, BUCKET) == []
