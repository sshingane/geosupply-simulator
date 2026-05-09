import streamlit as st
import pandas as pd

st.set_page_config(page_title="Data Explorer", page_icon="🔍", layout="wide")

from src.data_loader import load_all_data

st.title("🔍 Data Explorer")
st.markdown("Browse raw datasets with quality filters.")

dfs = load_all_data()

# Dataset selector
dataset_name = st.selectbox(
    "Select Dataset",
    [
        "trade_flows",
        "sanctions",
        "budgets",
        "energy",
        "macro",
        "companies",
    ],
    format_func=lambda x: {
        "trade_flows": "01 Semiconductor Trade Flows",
        "sanctions": "02 Trade Sanctions & Export Controls",
        "budgets": "03 National AI Infrastructure Budgets",
        "energy": "04 Energy Grid Capacity",
        "macro": "05 Macroeconomic Indicators",
        "companies": "06 Company Profiles",
    }.get(x, x),
)

df = dfs[dataset_name].copy()

# Filters
st.sidebar.header("Filters")

# Year filter if available
if "year" in df.columns:
    years = sorted(df["year"].unique().tolist())
    selected_years = st.sidebar.multiselect("Years", options=years, default=years)
    if selected_years:
        df = df[df["year"].isin(selected_years)]

# Country filter if available
country_col = None
for col in ["country_code", "exporter_country_code", "importer_country_code", "hq_country_code"]:
    if col in df.columns:
        country_col = col
        break

if country_col:
    countries = sorted(df[country_col].dropna().unique().tolist())
    selected_countries = st.sidebar.multiselect("Countries", options=countries, default=[])
    if selected_countries:
        df = df[df[country_col].isin(selected_countries)]

# Synthetic data filter
if "is_synthetic" in df.columns:
    show_synthetic = st.sidebar.checkbox("Include Synthetic Data", value=True)
    if not show_synthetic:
        df = df[df["is_synthetic"] == 0]
    # Add synthetic badge column
    df["data_quality"] = df["is_synthetic"].apply(lambda x: "🟡 Synthetic" if x == 1 else "🟢 Empirical")

st.subheader(f"{dataset_name.replace('_', ' ').title()} — {len(df)} rows")

# Display dataframe
st.dataframe(df, use_container_width=True)

# Download
st.sidebar.divider()
csv = df.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    label="Download Filtered CSV",
    data=csv,
    file_name=f"{dataset_name}_filtered.csv",
    mime="text/csv",
)
