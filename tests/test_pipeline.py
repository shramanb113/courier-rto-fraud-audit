from rto_audit.pipeline import run_pipeline


def test_run_pipeline_end_to_end_with_generated_data():
    result = run_pipeline(regenerate=True, n_couriers=12, n_events=600, seed=7)

    assert result.events_df.height > 0
    assert "distance_anomaly" in result.events_df.columns
    assert result.profile_df.height == 12
    assert "cluster_label" in result.clustered_df.columns
    assert result.agreement_df is not None
    assert result.agreement_df.height > 0
