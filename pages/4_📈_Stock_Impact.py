import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Stock Impact", page_icon="📈", layout="wide")

from src.data_loader import load_all_data, build_derived_tables, get_simulation_base_state
from src.stock_analyzer import (
    PUBLIC_TICKERS,
    PRIVATE_COMPANIES,
    fetch_all_stock_histories,
    get_all_market_caps,
    compute_historical_sanction_impact,
    predict_private_company_impact,
    find_closest_historical_sanction,
    YFINANCE_AVAILABLE,
)
from src.simulation_engine import ShockConfig, run_simulation
from src.viz import build_stock_projection_chart

st.title("📈 Stock Impact Analysis")
st.markdown(
    "Analyze how supply chain shocks affect semiconductor companies. "
    "Configure a shock below, then see estimated stock impacts with historical context."
)

# Help expander at top
with st.expander("How to read this page", expanded=False):
    st.markdown(
        """
        **What the percentage means:**
        - The **"Est. Stock Impact (90-day)"** percentage is our projection of how the company's stock price might move within 90 days of the simulated shock.
        - It is **not** a guaranteed prediction. It is an analytical estimate based on the company's trade exposure and a semiconductor sector revenue multiple (~4×).

        **How the chart works:**
        - **Gray solid line:** Historical stock price (2015–present).
        - **Red dashed line:** Projected price path after the shock, showing a gradual market reaction curve over 90 days.
        - **White dotted line:** The simulated shock date.

        **Historical validation:**
        - Where available, we show the closest real-world sanction event and its actual stock impact, so you can compare our estimate against ground truth.
        """
    )

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

    # --- Shock Context Header ---
    exporter_names = [base_state["baseline_countries"][base_state["baseline_countries"]["country_code"] == c]["country"].iloc[0] if not base_state["baseline_countries"][base_state["baseline_countries"]["country_code"] == c].empty else c for c in exporters]
    st.info(
        f"**Active Simulation:** Severity-{severity} {restriction_type.replace('_', ' ')} on "
        f"{', '.join(selected_hardware)} from {', '.join(exporter_names)} — "
        f"Estimated trade reduction: **${result.total_trade_reduction_millions:,.0f}M**"
    )

    # --- Summary Stats ---
    pub_impacts = result.company_impacts[result.company_impacts["company_name"].isin(PUBLIC_TICKERS.keys())]
    priv_impacts = result.company_impacts[result.company_impacts["company_name"].isin(PRIVATE_COMPANIES)]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Trade Reduction", f"${result.total_trade_reduction_millions:,.0f}M")
    s2.metric("Companies Affected", len(result.company_impacts))
    s3.metric("Public Companies", len(pub_impacts))
    s4.metric("Private Companies", len(priv_impacts))

    st.divider()

    # Tabs
    tab_public, tab_private = st.tabs(["📊 Publicly Traded", "🔒 Private / Predicted"])

    with tab_public:
        if pub_impacts.empty:
            st.info("No public companies directly affected by this shock.")
        else:
            st.subheader("Public Company Impact")

            for _, row in pub_impacts.iterrows():
                company = row["company_name"]
                ticker = PUBLIC_TICKERS.get(company, "N/A")
                impact = row["estimated_stock_impact_pct"]

                # Company card container
                with st.container(border=True):
                    # Header row
                    header_cols = st.columns([2, 1, 1])
                    with header_cols[0]:
                        st.markdown(f"### {company}")
                        caption = f"Ticker: `{ticker}`"
                        if company == "SMIC":
                            caption += " | 🇭🇰 Hong Kong only"
                        st.caption(caption)
                    with header_cols[1]:
                        st.metric(
                            label="Est. Stock Impact (90-day)",
                            value=f"{impact:+.1f}%",
                            help="Projected stock price change within 90 days of the shock, based on trade exposure × sector multiple (~4×).",
                        )
                    with header_cols[2]:
                        mc = market_caps.get(company)
                        if mc:
                            st.metric("Market Cap", f"${mc:.1f}B")
                        else:
                            st.caption("Market cap unavailable")

                    st.divider()

                    # Chart row
                    hist = stock_histories.get(company)
                    if hist is not None and not hist.empty:
                        date_col = "Date" if "Date" in hist.columns else "date"
                        latest_date = pd.to_datetime(hist[date_col].max())

                        fig = build_stock_projection_chart(
                            stock_df=hist,
                            estimated_impact_pct=impact,
                            shock_date=latest_date,
                            company_name=company,
                            ticker=ticker,
                            trade_hit_millions=row["trade_hit_millions"],
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No stock history available for chart.")

                    # Expandable sections
                    col_meth, col_hist = st.columns(2)

                    with col_meth:
                        with st.expander("Methodology"):
                            revenue = row["revenue_usd_bn"]
                            trade_hit = row["trade_hit_millions"]
                            rev_impact = row["revenue_impact_pct"] * 100
                            st.markdown(
                                f"""
                                **How this number was calculated:**

                                | Step | Value |
                                |------|-------|
                                | Trade Flow Disruption | ${trade_hit:,.0f}M |
                                | Annual Revenue | ${revenue:.1f}B |
                                | Revenue Impact | {rev_impact:.2f}% |
                                | Sector Multiple | 4.0× |
                                | **Est. Stock Impact** | **{impact:+.1f}%** |

                                The sector multiple of 4× is an empirical estimate for semiconductor stocks,
                                reflecting how markets typically price in revenue shocks.
                                """
                            )

                    with col_hist:
                        with st.expander("Historical Validation"):
                            closest = find_closest_historical_sanction(
                                sanctions=dfs["sanctions"],
                                restriction_type=restriction_type,
                                target_countries=[row["hq_country_code"]],
                                hardware_types=selected_hardware,
                                company_name=company,
                                stock_histories=stock_histories,
                            )
                            if closest:
                                sim_score = closest["similarity_score"]
                                actual = closest["actual_impact_pct"]
                                estimated_historical = closest["estimated_for_historical_pct"]
                                st.markdown(
                                    f"""
                                    **Closest Historical Event** (🔍 {sim_score:.0f}% match)

                                    - **Date:** {closest['date']}
                                    - **Event:** {closest['imposing_country']} imposed {closest['restriction_type'].replace('_', ' ')} on {closest['target_country']}
                                    - **Technology:** {closest['affected_technology']}
                                    - **Actual 90-day stock move:** {actual:+.1f}% if actual else "N/A"}%
                                    - **Our model would have estimated:** {estimated_historical:+.1f}%

                                    *This event is the most similar real-world sanction in our dataset.*
                                    """
                                )
                            else:
                                st.caption("No sufficiently similar historical event found in the dataset.")

    with tab_private:
        if priv_impacts.empty:
            st.info("No private companies directly affected by this shock.")
        else:
            st.subheader("Private Company Predicted Impact")

            for _, row in priv_impacts.iterrows():
                company = row["company_name"]
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

                with st.container(border=True):
                    header_cols = st.columns([2, 1, 1])
                    with header_cols[0]:
                        st.markdown(f"### {company}")
                        st.caption(f"Domain: {row['primary_domain']} | HQ: {row['hq_country_code']}")
                    with header_cols[1]:
                        st.metric(
                            label="Predicted Impact",
                            value=f"{prediction['predicted_impact_pct']:+.1f}%",
                            help="Rule-based prediction using comparable public companies. NOT market data.",
                        )
                    with header_cols[2]:
                        st.caption(f"Method: {prediction['method']}")
                        st.caption(f"Confidence: {prediction['confidence']}")

                    st.warning("⚠️ PREDICTED — NOT MARKET DATA")

                    with st.expander("How we predicted this"):
                        st.markdown(
                            f"""
                            **Methodology:**

                            1. **Trade Exposure:** ${row['trade_hit_millions']:,.0f}M in disrupted trade flows
                            2. **Comparable Companies:** {', '.join(prediction['comparables_used']) if prediction['comparables_used'] else 'None found — used analytical fallback'}
                            3. **Scaling:** Adjusted by revenue ratio vs. comparables
                            4. **Geo-Risk Adjustment:** {geo_delta:+.2f} (based on HQ country trajectory)

                            **Limitations:**
                            - Private companies have no market price history
                            - Prediction relies on extrapolation from public peers
                            - Actual impact could differ significantly
                            """
                        )

                    with st.expander("What would change this?"):
                        st.markdown(
                            """
                            - If this company goes public, we could use real market data
                            - If more detailed revenue-by-region data becomes available, exposure calculation improves
                            - If historical private-company valuation rounds exist, we could correlate against those
                            """
                        )

else:
    st.info("Configure a shock in the sidebar and click **Run Impact Analysis**.")
