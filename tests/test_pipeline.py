from rto_audit.datagen import generate_delivery_logs
from rto_audit.pipeline import run_pipeline


def test_run_pipeline_end_to_end_with_generated_data():
    result = run_pipeline(regenerate=True, n_couriers=12, n_events=600, seed=7)

    assert result.events_df.height > 0
    assert "distance_anomaly" in result.events_df.columns
    assert result.profile_df.height == 12
    assert "cluster_label" in result.clustered_df.columns
    assert result.agreement_df is not None
    assert result.agreement_df.height > 0


def test_run_pipeline_accepts_preloaded_events_df():
    events_df, _ = generate_delivery_logs(n_couriers=5, n_events=100, seed=3)

    result = run_pipeline(events_df=events_df)

    assert result.events_df.height == events_df.height
    assert "distance_anomaly" in result.events_df.columns
    assert result.profile_df.height == 5
    assert "cluster_label" in result.clustered_df.columns
    assert result.agreement_df is None
