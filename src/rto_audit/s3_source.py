from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import boto3
import polars as pl


def get_s3_client(endpoint_url: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def ensure_bucket(client, bucket: str) -> None:
    existing = client.list_buckets().get("Buckets", [])
    if not any(b["Name"] == bucket for b in existing):
        client.create_bucket(Bucket=bucket)


def upload_batch(client, bucket: str, events_df: pl.DataFrame) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    key = f"events/{timestamp}-{uuid.uuid4().hex[:8]}.csv"

    buffer = io.BytesIO()
    events_df.write_csv(buffer)
    client.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
    return key


def list_batch_keys(client, bucket: str) -> list[str]:
    response = client.list_objects_v2(Bucket=bucket, Prefix="events/")
    return sorted(obj["Key"] for obj in response.get("Contents", []))


def download_batch(client, bucket: str, key: str) -> pl.DataFrame:
    response = client.get_object(Bucket=bucket, Key=key)
    return pl.read_csv(response["Body"].read(), try_parse_dates=True)
