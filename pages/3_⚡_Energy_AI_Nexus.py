import streamlit as st
import pandas as pd

st.set_page_config(page_title="Energy-AI Nexus", page_icon="⚡", layout="wide")

from src.data_loader import load_all_data, build_derived_tables
from src.viz import build_energy_scatter, build_energy_time_series

st.title("⚡ Energy-AI Nexus")
st.markdown("Explore the collision between AI datacenter energy demand and grid capacity.")

dfs = load_all_data()
derived = build_derived_tables(dfs)

country_profiles = derived["country_profiles"]
energy = dfs["energy"]

# Filters
st.sidebar.header("Filters")
available_countries = sorted(energy["country_code"].unique().tolist())
selected_countries = st.sidebar.multiselect(
    "Countries",
    options=available_countries,
    default=available_countries[:5],
)

year_range = st.sidebar.slider(
    "Year Range",
    int(energy["year"].min()),
    int(energy["year"].max()),
    (int(energy["year"].min()), int(energy["year"].max())),
)

# Filter data
filtered_energy = energy[
    (energy["country_code"].isin(selected_countries))
    & (energy["year"] >= year_range[0])
    & (energy["year"] <= year_range[1])
].copy()

filtered_profiles = country_profiles[
    (country_profiles["country_code"].isin(selected_countries))
    & (country_profiles["year"] >= year_range[0])
    & (country_profiles["year"] <= year_range[1])
].copy()

# Merge for scatter plot
scatter_df = filtered_profiles.merge(
    filtered_energy[["country_code", "year", "renewable_energy_pct", "pct_grid_used_by_ai", "ai_grid_stress_index", "energy_constraint_level"]],
    on=["country_code", "year"],
    how="inner",
)

# Scatter plot
st.subheader("Renewable Energy vs AI Grid Use")
if not scatter_df.empty:
    fig1 = build_energy_scatter(scatter_df)
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.warning("No data available for the selected filters.")

# Time series
st.subheader("AI Datacenter Energy Over Time")
if not filtered_energy.empty:
    fig2 = build_energy_time_series(filtered_energy, countries=selected_countries)
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.warning("No data available for the selected filters.")

# Warning table
st.subheader("Grid Stress Warnings")
warnings = filtered_energy[filtered_energy["ai_grid_stress_index"] > 0.5].copy()
if warnings.empty:
    warnings = filtered_energy[filtered_energy["energy_constraint_level"].isin(["High", "Critical"])].copy()

if not warnings.empty:
    warnings = warnings.sort_values("ai_grid_stress_index", ascending=False)
    st.dataframe(
        warnings[
            ["country", "year", "ai_grid_stress_index", "pct_grid_used_by_ai", "energy_constraint_level", "planned_expansion_gw"]
        ]
    )
else:
    st.info("No grid stress warnings for the selected filters.")

# Carbon intensity table
st.subheader("Carbon Intensity per AI Investment")
if not filtered_profiles.empty and "total_ai_investment_usd_bn" in filtered_profiles.columns:
    carbon_df = filtered_profiles.copy()
    carbon_df = carbon_df.merge(
        filtered_energy[["country_code", "year", "carbon_intensity_gco2_per_kwh"]],
        on=["country_code", "year"],
        how="inner",
    )
    carbon_df["carbon_per_ai_invest"] = (
        carbon_df["carbon_intensity_gco2_per_kwh"] / carbon_df["total_ai_investment_usd_bn"].replace(0, pd.NA)
    )
    carbon_df = carbon_df.sort_values("carbon_per_ai_invest", ascending=False)
    st.dataframe(
        carbon_df[["country", "year", "carbon_intensity_gco2_per_kwh", "total_ai_investment_usd_bn", "carbon_per_ai_invest"]]
    )
else:
    st.info("Carbon intensity data not available for selected filters.")

# Download
st.sidebar.divider()
if st.sidebar.button("Download Filtered Energy Data"):
    csv = filtered_energy.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Download CSV",
        data=csv,
        file_name="energy_data.csv",
        mime="text/csv",
    )
