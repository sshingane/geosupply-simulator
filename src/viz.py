"""Reusable visualization builders for Plotly maps and charts."""
from typing import List, Optional

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from src.geo_utils import COUNTRY_CODE_TO_LATLON, get_region_color_map


def build_choropleth_map(
    df: pd.DataFrame,
    color_col: str,
    hover_cols: Optional[List[str]] = None,
    color_scale: str = "RdYlBu_r",
    title: str = "",
    zoom_to_affected: bool = False,
    affected_codes: Optional[List[str]] = None,
) -> go.Figure:
    """Build a Plotly choropleth world map."""
    fig = px.choropleth(
        df,
        locations="iso3",
        color=color_col,
        hover_name="country",
        hover_data=hover_cols or [],
        color_continuous_scale=color_scale,
        scope="world",
        title=title,
    )

    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type="equirectangular",
        ),
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    if zoom_to_affected and affected_codes:
        lats, lons = [], []
        for code in affected_codes:
            lat, lon = COUNTRY_CODE_TO_LATLON.get(code, (0, 0))
            if lat != 0 or lon != 0:
                lats.append(lat)
                lons.append(lon)
        if lats and lons:
            fig.update_geos(
                lonaxis_range=[min(lons) - 15, max(lons) + 15],
                lataxis_range=[min(lats) - 15, max(lats) + 15],
            )

    return fig


def add_trade_routes(fig: go.Figure, trade_df: pd.DataFrame, disrupted_only: bool = False) -> go.Figure:
    """Overlay trade route arrows on a map."""
    if disrupted_only:
        df = trade_df[trade_df["trade_reduction"] > 0].copy()
    else:
        df = trade_df.copy()

    for _, row in df.iterrows():
        exp_code = row["exporter_country_code"]
        imp_code = row["importer_country_code"]
        exp_lat, exp_lon = COUNTRY_CODE_TO_LATLON.get(exp_code, (0, 0))
        imp_lat, imp_lon = COUNTRY_CODE_TO_LATLON.get(imp_code, (0, 0))

        if exp_lat == 0 and exp_lon == 0:
            continue
        if imp_lat == 0 and imp_lon == 0:
            continue

        is_disrupted = row.get("trade_reduction", 0) > 0
        width = max(1, min(8, row.get("trade_value_usd_millions", 0) / 200))
        color = "#FF4444" if is_disrupted else "#4488FF"
        opacity = 0.7 if is_disrupted else 0.3

        fig.add_trace(
            go.Scattergeo(
                lon=[exp_lon, imp_lon],
                lat=[exp_lat, imp_lat],
                mode="lines",
                line=dict(width=width, color=color),
                opacity=opacity,
                hoverinfo="text",
                text=f"{row.get('exporter_country', exp_code)} -> {row.get('importer_country', imp_code)}<br>"
                f"Hardware: {row.get('hardware_type', 'N/A')}<br>"
                f"Baseline: ${row.get('trade_value_usd_millions', 0):.1f}M<br>"
                f"Reduction: ${row.get('trade_reduction', 0):.1f}M",
                showlegend=False,
            )
        )

    return fig


def build_sovereignty_delta_chart(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Bar chart of sovereignty index changes."""
    df = df.copy()
    df["abs_delta"] = df["sovereignty_delta"].abs()
    df = df.nlargest(top_n, "abs_delta").sort_values("sovereignty_delta")

    colors = ["#2ca02c" if x > 0 else "#d62728" for x in df["sovereignty_delta"]]

    fig = go.Figure(
        go.Bar(
            x=df["sovereignty_delta"],
            y=df["country"],
            orientation="h",
            marker_color=colors,
            text=[f"{x:+.2f}" for x in df["sovereignty_delta"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="AI Sovereignty Index Change",
        xaxis_title="Delta",
        yaxis_title="",
        margin={"l": 100, "r": 20, "t": 40, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def build_energy_stress_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of AI grid stress changes."""
    df = df.copy()
    df = df[df["grid_stress_delta"] != 0].sort_values("grid_stress_delta")

    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No Energy Grid Stress Changes")
        return fig

    colors = ["#2ca02c" if x < 0 else "#d62728" for x in df["grid_stress_delta"]]

    fig = go.Figure(
        go.Bar(
            x=df["grid_stress_delta"],
            y=df["country"],
            orientation="h",
            marker_color=colors,
            text=[f"{x:+.3f}" for x in df["grid_stress_delta"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="AI Grid Stress Index Change",
        xaxis_title="Delta",
        yaxis_title="",
        margin={"l": 100, "r": 20, "t": 40, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def build_company_impact_chart(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Bar chart of estimated stock impact for companies."""
    df = df.copy()
    df = df.nlargest(top_n, "estimated_stock_impact_pct").sort_values("estimated_stock_impact_pct")

    colors = ["#d62728"] * len(df)

    fig = go.Figure(
        go.Bar(
            x=df["estimated_stock_impact_pct"],
            y=df["company_name"],
            orientation="h",
            marker_color=colors,
            text=[f"{x:.1f}%" for x in df["estimated_stock_impact_pct"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Estimated Stock Impact",
        xaxis_title="Estimated Impact (%)",
        yaxis_title="",
        margin={"l": 120, "r": 20, "t": 40, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def build_energy_scatter(df: pd.DataFrame) -> go.Figure:
    """Scatter plot: renewable % vs AI grid use %."""
    fig = px.scatter(
        df,
        x="renewable_energy_pct",
        y="pct_grid_used_by_ai",
        size="total_ai_investment_usd_bn",
        color="region",
        hover_name="country",
        hover_data=["year", "ai_grid_stress_index", "energy_constraint_level"],
        color_discrete_map=get_region_color_map(),
        title="Renewable Energy % vs AI Datacenter Grid Use %",
    )
    fig.update_layout(
        xaxis_title="Renewable Energy %",
        yaxis_title="Grid Used by AI %",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def build_energy_time_series(df: pd.DataFrame, countries: Optional[List[str]] = None) -> go.Figure:
    """Time series of AI datacenter energy TWh."""
    if countries:
        df = df[df["country_code"].isin(countries)]

    fig = px.line(
        df,
        x="year",
        y="ai_datacenter_energy_twh",
        color="country",
        markers=True,
        title="AI Datacenter Energy Consumption (TWh)",
    )
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="TWh",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def build_stock_projection_chart(
    stock_df: pd.DataFrame,
    estimated_impact_pct: float,
    shock_date: pd.Timestamp,
    company_name: str,
    ticker: str,
    trade_hit_millions: float,
) -> go.Figure:
    """Build a chart showing historical price + projected post-shock trajectory."""
    if stock_df is None or stock_df.empty:
        fig = go.Figure()
        fig.update_layout(title="No stock data available")
        return fig

    date_col = "Date" if "Date" in stock_df.columns else "date"
    stock_df = stock_df.copy()
    stock_df[date_col] = pd.to_datetime(stock_df[date_col])
    stock_df = stock_df.sort_values(date_col)

    # Historical line (up to shock date)
    historical = stock_df[stock_df[date_col] <= shock_date].copy()
    latest_price = historical["Close"].iloc[-1] if not historical.empty else stock_df["Close"].iloc[-1]
    latest_date = historical[date_col].iloc[-1] if not historical.empty else stock_df[date_col].iloc[-1]

    # Projected trajectory: 90 days post-shock with exponential decay recovery
    projection_days = 90
    projected_dates = pd.date_range(
        start=latest_date + pd.Timedelta(days=1),
        periods=projection_days,
        freq="D",
    )

    # Exponential decay curve: steepest drop in first 2 weeks, then gradual stabilization
    # Model: price(t) = baseline * (1 + impact * (0.3 + 0.7 * exp(-t/30)))
    # where impact is negative for a drop
    # At t=0: price = baseline * (1 + impact)
    # At t=30: price = baseline * (1 + impact * 0.3 + 0.7 * exp(-1)) ≈ baseline * (1 + impact * 0.56)
    # At t=90: price = baseline * (1 + impact * 0.3 + 0.7 * exp(-3)) ≈ baseline * (1 + impact * 0.33)
    t = np.arange(1, projection_days + 1)
    decay_factor = 0.3 + 0.7 * np.exp(-t / 30.0)
    projected_prices = latest_price * (1 + (estimated_impact_pct / 100) * decay_factor)

    projected_df = pd.DataFrame({
        date_col: projected_dates,
        "Close": projected_prices,
        "type": "projected",
    })

    historical["type"] = "historical"

    fig = go.Figure()

    # Historical line
    fig.add_trace(
        go.Scatter(
            x=historical[date_col],
            y=historical["Close"],
            mode="lines",
            name="Historical",
            line=dict(color="#888888", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Price: $%{y:.2f}<extra>Historical</extra>",
        )
    )

    # Projected line
    fig.add_trace(
        go.Scatter(
            x=projected_df[date_col],
            y=projected_df["Close"],
            mode="lines",
            name="Projected",
            line=dict(color="#FF4444", width=2, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}<br>Projected: $%{y:.2f}<extra>Projected</extra>",
        )
    )

    # Shock date vertical line
    fig.add_shape(
        type="line",
        x0=latest_date,
        x1=latest_date,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="#FFFFFF", width=1, dash="dot"),
    )
    fig.add_annotation(
        x=latest_date,
        y=1.0,
        yref="paper",
        text="Shock",
        showarrow=False,
        font=dict(color="#FFFFFF", size=10),
        bgcolor="rgba(0,0,0,0.5)",
    )

    # Annotation for projected impact
    target_price = projected_prices[-1]
    fig.add_annotation(
        x=projected_dates[-1],
        y=target_price,
        text=f"Est. 90-day: ${target_price:.2f} ({estimated_impact_pct:+.1f}%)",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#FF4444",
        font=dict(color="#FF4444", size=12),
        bgcolor="rgba(0,0,0,0.7)",
    )

    fig.update_layout(
        title=f"{company_name} ({ticker}) — Historical & Projected",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin={"l": 50, "r": 50, "t": 60, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )

    return fig
