import plotly.express as px
import polars as pl
import streamlit as st

from rto_audit.clustering import LABEL_HIGH_RISK
from rto_audit.config import COST_PER_RTO_RANGE_INR, DEFAULT_COST_PER_RTO_INR
from rto_audit.pipeline import run_pipeline

st.set_page_config(page_title="Courier Telemetry Audit", layout="wide")


@st.cache_data
def load_pipeline_result(seed: int):
    return run_pipeline(regenerate=True, n_couriers=50, n_events=20_000, seed=seed)


result = load_pipeline_result(seed=42)

st.title("Courier Telemetry Audit & RTO Fraud Analytics")

tab_leakage, tab_leaderboard, tab_geo = st.tabs(
    ["Company-Wide Leakage", "Leaderboard of Concern", "Geospatial Clusters"]
)

with tab_leakage:
    st.subheader("Estimated Capital Lost to Fake RTO Attempts")
    cost_per_rto = st.slider(
        "Cost per reverse-logistics loop (INR)",
        min_value=COST_PER_RTO_RANGE_INR[0],
        max_value=COST_PER_RTO_RANGE_INR[1],
        value=DEFAULT_COST_PER_RTO_INR,
    )
    high_risk_anomalies = result.events_df.filter(pl.col("distance_anomaly") == 1).join(
        result.clustered_df.select(["courier_id", "cluster_label"]), on="courier_id"
    ).filter(pl.col("cluster_label") == LABEL_HIGH_RISK)
    total_anomalies = high_risk_anomalies.height
    total_leakage = total_anomalies * cost_per_rto

    col1, col2 = st.columns(2)
    col1.metric("Total Flagged Anomaly Events (High-Risk Cluster)", total_anomalies)
    col2.metric("Estimated Leakage (INR)", f"₹{total_leakage:,.0f}")

    by_cluster = (
        result.events_df.filter(pl.col("distance_anomaly") == 1)
        .join(result.clustered_df.select(["courier_id", "cluster_label"]), on="courier_id")
        .group_by("cluster_label")
        .agg(pl.len().alias("anomaly_events"))
        .with_columns((pl.col("anomaly_events") * cost_per_rto).alias("estimated_leakage_inr"))
        .sort("estimated_leakage_inr", descending=True)
    )
    st.dataframe(by_cluster.to_pandas(), use_container_width=True)

with tab_leaderboard:
    st.subheader("Top 20 Couriers by Distance Deviation")
    st.caption(
        "Labels reflect a statistical pattern, not confirmed fraud. GPS multipath in dense "
        "urban areas and merchant address errors can also produce high deviation — treat this "
        "as a ~75% confidence signal requiring manual audit, not a verdict."
    )
    leaderboard = (
        result.clustered_df.sort("avg_deviation_distance", descending=True)
        .head(20)
        .select(["courier_id", "cluster_label", "rto_rate", "anomaly_count", "avg_deviation_distance"])
    )
    st.dataframe(leaderboard.to_pandas(), use_container_width=True)

with tab_geo:
    st.subheader("Courier Risk Clusters")
    fig = px.scatter(
        result.clustered_df.to_pandas(),
        x="avg_deviation_distance",
        y="rto_rate",
        color="cluster_label",
        hover_data=["courier_id", "anomaly_count", "distance_variance"],
        labels={"avg_deviation_distance": "Avg. Deviation Distance (m)", "rto_rate": "RTO Rate"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Flagged Events for Top Leaderboard Couriers")
    top_courier_ids = leaderboard["courier_id"].head(5).to_list()
    flagged_events = result.events_df.filter(
        (pl.col("distance_anomaly") == 1) & (pl.col("courier_id").is_in(top_courier_ids))
    )
    map_fig = px.scatter_mapbox(
        flagged_events.to_pandas(),
        lat="courier_latitude",
        lon="courier_longitude",
        hover_name="courier_id",
        zoom=9,
        height=500,
    )
    map_fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(map_fig, use_container_width=True)
