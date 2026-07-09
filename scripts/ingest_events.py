from rto_audit.config import DATABASE_URL, S3_BUCKET_NAME, S3_ENDPOINT_URL
from rto_audit.ingest import run_and_store_from_s3
from rto_audit.s3_source import ensure_bucket, get_s3_client
from rto_audit.store import get_engine, init_schema


def main() -> None:
    engine = get_engine(DATABASE_URL)
    init_schema(engine)

    client = get_s3_client(endpoint_url=S3_ENDPOINT_URL)
    ensure_bucket(client, S3_BUCKET_NAME)

    run_id = run_and_store_from_s3(engine, client, S3_BUCKET_NAME)
    print(f"Ingested S3 batches into run #{run_id}")


if __name__ == "__main__":
    main()
