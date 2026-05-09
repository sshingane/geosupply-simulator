import streamlit as st
import pandas as pd

st.set_page_config(page_title="Stock Impact", page_icon="📈", layout="wide")

from src.data_loader import load_all_data, build_derived_tables, get_simulation_base_state
from src.stock_analyzer import (
    PUBLIC_TICKERS,
    PRIVATE_COMPANIES,
    fetch_all_stock_histories,
    get_all_market_caps,
    compute_historical_sanction_impact,
    predict_private_company_impact,
    YFINANCE_AVAILABLE,
)
from src.simulation_engine import ShockConfig, run_simulation

st.title("📈 Stock Impact Analysis")
st.markdown("Analyze how supply chain shocks affect semiconductor companies.")

dfs = load_all_data()
derived = build_derived_tables(dfs)
base_state = get_simulation_base_state(dfs)

# Sidebar: Simulation input
with st.sidebar:
    st.header("Simulation Input")
    exporters = st.multiselect(
        "Exporter Countries",
        options=sorted(base_state["baseline_countries"]["country_code"].unique().tolist()),
        default=["TW"],
    )
    hardware_types = sorted(dfs["trade_flows"]["hardware_type"].unique().tolist())
    selected_hardware = st.multiselect(
        "Hardware Types",
        options=hardware_types,
        default=["Advanced_Logic_Chip"],
    )
    restriction_type = st.selectbox(
        "Restriction Type",
        ["Export_Ban", "Tariff", "License_Requirement", "Technology_Transfer_Ban"],
    )
    severity = st.slider("Severity", 1, 5, 4)

    run_sim = st.button("Run Impact Analysis", type="primary", use_container_width=True)

# Tabs for Public / Private
tab_public, tab_private = st.tabs(["Publicly Traded", "Private / Predicted"])

# Pre-fetch stock data
if YFINANCE_AVAILABLE:
    with st.spinner("Loading stock histories..."):
        stock_histories = fetch_all_stock_histories()
        market_caps = get_all_market_caps()
else:
    stock_histories = {}
    market_caps = {}
    st.warning("yfinance not installed. Stock data unavailable. Install with: `pip install yfinance`")

# Run simulation
if run_sim and exporters and selected_hardware:
    with st.spinner("Running simulation..."):
        shocks = [ShockConfig(
            exporters=exporters,
            hardware_types=selected_hardware,
            restriction_type=restriction_type,
            severity=severity,
            duration_quarters=4,
        )]
        result = run_simulation(
            shocks=shocks,
            trade_flows=base_state["trade_flows"],
            country_baseline=base_state["baseline_countries"],
            energy_data=dfs["energy"],
            company_exposure=derived["company_exposure"],
        )

    with tab_public:
        st.subheader("Public Company Impact")
        if result.company_impacts.empty:
            st.info("No public companies directly affected by this shock.")
        else:
            public_impacts = result.company_impacts[
                result.company_impacts["company_name"].isin(PUBLIC_TICKERS.keys())
            ].copy()

            if public_impacts.empty:
                st.info("No public companies directly affected by this shock.")
            else:
                for _, row in public_impacts.iterrows():
                    company = row["company_name"]
                    ticker = PUBLIC_TICKERS.get(company, "N/A")
                    col1, col2, col3 = st.columns([1, 1, 2])

                    with col1:
                        st.metric(company, f"{row['estimated_stock_impact_pct']:.1f}%")
                        st.caption(f"Ticker: {ticker}")
                        if company == "SMIC":
                            st.caption("🇭🇰 Hong Kong only")

                    with col2:
                        st.write(f"Revenue: ${row['revenue_usd_bn']:.1f}B")
                        st.write(f"Trade Hit: ${row['trade_hit_millions']:.0f}M")
                        mc = market_caps.get(company)
                        if mc:
                            st.write(f"Market Cap: ${mc:.1f}B")

                    with col3:
                        # Historical chart
                        hist = stock_histories.get(company)
                        if hist is not None and not hist.empty:
                            date_col = "Date" if "Date" in hist.columns else "date"
                            st.line_chart(hist.set_index(date_col)["Close"])
                        else:
                            st.caption("No stock history available.")

                    st.divider()

    with tab_private:
        st.subheader("Private Company Predicted Impact")
        private_impacts = result.company_impacts[
            result.company_impacts["company_name"].isin(PRIVATE_COMPANIES)
        ].copy()

        if private_impacts.empty:
            st.info("No private companies directly affected by this shock.")
        else:
            for _, row in private_impacts.iterrows():
                company = row["company_name"]
                # Get geo risk delta for HQ country
                hq_row = base_state["baseline_countries"][
                    base_state["baseline_countries"]["country_code"] == row["hq_country_code"]
                ]
                geo_delta = 0.0
                if not hq_row.empty:
                    geo_delta = hq_row.iloc[0].get("geopolitical_risk_score", 0) * 0.1

                prediction = predict_private_company_impact(
                    company_name=company,
                    domain=row["primary_domain"],
                    revenue=row["revenue_usd_bn"],
                    hq_country_code=row["hq_country_code"],
                    trade_hit_millions=row["trade_hit_millions"],
                    country_geo_risk_delta=geo_delta,
                    company_exposure=derived["company_exposure"],
                    stock_histories=stock_histories,
                    sanctions=dfs["sanctions"],
                )

                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric(company, f"{prediction['predicted_impact_pct']:.1f}%")
                    st.caption(f"Method: {prediction['method']}")
                    st.caption(f"Confidence: {prediction['confidence']}")
                    if prediction["comparables_used"]:
                        st.caption(f"Comparables: {', '.join(prediction['comparables_used'])}")

                with col2:
                    st.write(f"Revenue: ${row['revenue_usd_bn']:.1f}B")
                    st.write(f"Trade Hit: ${row['trade_hit_millions']:.0f}M")
                    st.write(f"Domain: {row['primary_domain']}")

                st.warning("⚠️ PREDICTED — NOT MARKET DATA")
                st.divider()

else:
    st.info("Configure a shock in the sidebar and click **Run Impact Analysis**.")
