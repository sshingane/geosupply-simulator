import streamlit as st
import pandas as pd

st.set_page_config(page_title="Geopolitical Simulator", page_icon="🌍", layout="wide")

from src.data_loader import load_all_data, build_derived_tables, get_simulation_base_state
from src.geo_utils import add_iso3, add_latlon
from src.simulation_engine import (
    ShockConfig,
    run_simulation,
    scenario_taiwan_strait_crisis,
    scenario_full_china_export_ban,
    scenario_chips_act_acceleration,
    scenario_eu_energy_constraint,
)
from src.viz import (
    build_choropleth_map,
    add_trade_routes,
    build_sovereignty_delta_chart,
    build_energy_stress_chart,
    build_company_impact_chart,
)

st.title("🌍 Geopolitical Simulator")
st.markdown("Configure supply chain shocks and visualize global impacts.")

# Load data
dfs = load_all_data()
derived = build_derived_tables(dfs)
base_state = get_simulation_base_state(dfs)

# Sidebar: Configuration
with st.sidebar:
    st.header("Shock Configuration")

    preset = st.selectbox(
        "Load Preset Scenario",
        [
            "Custom",
            "Taiwan Strait Crisis",
            "Full China Export Ban",
            "CHIPS Act Acceleration",
            "EU Energy Constraint",
        ],
    )

    shocks = []
    if preset == "Taiwan Strait Crisis":
        shocks = scenario_taiwan_strait_crisis()
        st.info("Taiwan export ban on Advanced Logic Chips, severity 4, 4 quarters.")
    elif preset == "Full China Export Ban":
        shocks = scenario_full_china_export_ban()
        st.info("China export ban on all hardware, severity 5, 8 quarters.")
    elif preset == "CHIPS Act Acceleration":
        shocks = scenario_chips_act_acceleration()
        st.info("US tariffs on TW/KR/JP chips to boost domestic capacity.")
    elif preset == "EU Energy Constraint":
        shocks = scenario_eu_energy_constraint()
        st.info("DE/NL license requirements due to grid stress.")

    st.divider()
    st.subheader("Custom Shock")

    exporters = st.multiselect(
        "Exporter Countries",
        options=sorted(base_state["baseline_countries"]["country_code"].unique().tolist()),
        default=shocks[0].exporters if shocks else [],
    )

    hardware_types = sorted(dfs["trade_flows"]["hardware_type"].unique().tolist())
    selected_hardware = st.multiselect(
        "Hardware Types",
        options=hardware_types,
        default=shocks[0].hardware_types if shocks else [hardware_types[0]],
    )

    restriction_type = st.selectbox(
        "Restriction Type",
        ["Export_Ban", "Tariff", "License_Requirement", "Technology_Transfer_Ban"],
        index=0 if not shocks else ["Export_Ban", "Tariff", "License_Requirement", "Technology_Transfer_Ban"].index(shocks[0].restriction_type),
    )

    severity = st.slider("Severity", 1, 5, value=shocks[0].severity if shocks else 3)
    duration = st.slider("Duration (quarters)", 1, 12, value=shocks[0].duration_quarters if shocks else 4)

    if st.button("Run Simulation", type="primary", use_container_width=True):
        if exporters and selected_hardware:
            shocks = [ShockConfig(
                exporters=exporters,
                hardware_types=selected_hardware,
                restriction_type=restriction_type,
                severity=severity,
                duration_quarters=duration,
            )]
        else:
            st.warning("Please select at least one exporter and hardware type.")
            shocks = []

# Run simulation if shocks exist
if shocks:
    with st.spinner("Running simulation..."):
        result = run_simulation(
            shocks=shocks,
            trade_flows=base_state["trade_flows"],
            country_baseline=base_state["baseline_countries"],
            energy_data=dfs["energy"],
            company_exposure=derived["company_exposure"],
        )

    # Metrics row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trade Reduction", f"${result.total_trade_reduction_millions:,.0f}M")
    m2.metric("Exporters Affected", len(result.affected_exporter_countries))
    m3.metric("Importers Affected", len(result.affected_importer_countries))
    m4.metric("Companies Hit", len(result.company_impacts))

    # Map + Charts
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Global Impact Map")
        map_df = add_iso3(result.shocked_countries)
        map_df = add_latlon(map_df, "country_code")
        map_df["iso3"] = map_df["iso3"].fillna("")

        fig = build_choropleth_map(
            map_df,
            color_col="geo_risk_delta",
            hover_cols=["baseline_geo_risk", "new_geo_risk", "sovereignty_delta"],
            title="Geopolitical Risk Score Change",
            zoom_to_affected=True,
            affected_codes=result.affected_exporter_countries + result.affected_importer_countries,
        )

        # Add trade routes
        fig = add_trade_routes(fig, result.trade_impacts, disrupted_only=True)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Sovereignty Impact")
        fig2 = build_sovereignty_delta_chart(result.shocked_countries, top_n=10)
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Energy Grid Stress")
        fig3 = build_energy_stress_chart(result.energy_impacts)
        st.plotly_chart(fig3, use_container_width=True)

    # Company impacts
    st.subheader("Company Exposure")
    fig4 = build_company_impact_chart(result.company_impacts, top_n=15)
    st.plotly_chart(fig4, use_container_width=True)

    # Detailed tables
    with st.expander("View Detailed Trade Impacts"):
        st.dataframe(result.trade_impacts.sort_values("trade_reduction", ascending=False))

    with st.expander("View Country Metrics"):
        st.dataframe(result.shocked_countries.sort_values("geo_risk_delta", ascending=False))

    with st.expander("View Company Impacts"):
        st.dataframe(result.company_impacts.sort_values("estimated_stock_impact_pct", ascending=False))

else:
    st.info("Configure a shock in the sidebar and click **Run Simulation** to see results.")
