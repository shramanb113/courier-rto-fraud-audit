from sqlalchemy import create_engine

from rto_audit.ingest import run_and_store
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
