"""Reusable visualization builders for Plotly maps and charts."""
from typing import List, Optional

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
