import argparse
from datetime import datetime, timezone

from rto_audit.config import S3_BUCKET_NAME, S3_ENDPOINT_URL
from rto_audit.datagen import generate_delivery_logs
from rto_audit.s3_source import ensure_bucket, get_s3_client, upload_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate a courier telemetry feed by uploading a batch of "
        "synthetic events to the S3 bucket."
    )
    parser.add_argument("--couriers", type=int, default=10)
    parser.add_argument("--events", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else int(datetime.now(timezone.utc).timestamp())
    events_df, _ = generate_delivery_logs(n_couriers=args.couriers, n_events=args.events, seed=seed)

    client = get_s3_client(endpoint_url=S3_ENDPOINT_URL)
    ensure_bucket(client, S3_BUCKET_NAME)
    key = upload_batch(client, S3_BUCKET_NAME, events_df)

    print(f"Uploaded {events_df.height} events for {args.couriers} couriers to s3://{S3_BUCKET_NAME}/{key}")


if __name__ == "__main__":
    main()
