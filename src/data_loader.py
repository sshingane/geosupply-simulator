"""Data loading and linking for GeoSupply AI Simulator."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st


def _data_dir() -> Path:
    """Return path to raw data directory."""
    # When running from repo root
    candidate = Path(__file__).parent.parent / "data" / "raw"
    if candidate.exists():
        return candidate
    # Fallback for odd working directories
    return Path("data/raw")


@st.cache_data(show_spinner="Loading datasets...")
def load_all_data() -> dict[str, pd.DataFrame]:
    """Load and return all six source tables."""
    d = _data_dir()
    return {
        "trade_flows": pd.read_csv(d / "01_semiconductor_trade_flows.csv"),
        "sanctions": pd.read_csv(d / "02_trade_sanctions_export_controls.csv"),
        "budgets": pd.read_csv(d / "03_national_ai_infrastructure_budgets.csv"),
        "energy": pd.read_csv(d / "04_energy_grid_capacity.csv"),
        "macro": pd.read_csv(d / "05_macroeconomic_indicators.csv"),
        "companies": pd.read_csv(d / "06_company_profiles.csv"),
    }


@st.cache_data(show_spinner="Building derived tables...")
def build_derived_tables(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Create derived tables by linking source tables."""
    trade = dfs["trade_flows"].copy()
    budgets = dfs["budgets"].copy()
    energy = dfs["energy"].copy()
    macro = dfs["macro"].copy()
    companies = dfs["companies"].copy()

    # --- Country Profiles: merge budgets + energy + macro on (country_code, year) ---
    country_profiles = budgets.merge(
        energy, on=["country_code", "country", "region", "year"], how="outer", suffixes=("", "_energy")
    )
    country_profiles = country_profiles.merge(
        macro, on=["country_code", "country", "region", "year"], how="outer", suffixes=("", "_macro")
    )
    # Drop duplicated columns from suffixes
    for col in list(country_profiles.columns):
        if col.endswith("_energy") or col.endswith("_macro"):
            base = col.replace("_energy", "").replace("_macro", "")
            if base in country_profiles.columns:
                country_profiles.drop(columns=[col], inplace=True)
            else:
                country_profiles.rename(columns={col: base}, inplace=True)

    # --- Trade Network: edge list from trade_flows ---
    trade_network = (
        trade.groupby(
            [
                "exporter_country_code",
                "exporter_country",
                "exporter_region",
                "importer_country_code",
                "importer_country",
                "importer_region",
                "hardware_type",
                "hardware_category",
                "trade_route",
            ]
        )
        .agg(
            total_volume_units=("volume_units", "sum"),
            total_trade_value_usd_millions=("trade_value_usd_millions", "sum"),
            avg_restriction_factor=("restriction_factor", "mean"),
            avg_geo_risk_exporter=("geo_risk_score_exporter", "mean"),
            avg_geo_risk_importer=("geo_risk_score_importer", "mean"),
            years_active=("year", lambda s: sorted(s.unique().tolist())),
        )
        .reset_index()
    )

    # --- Company Exposure: map companies to trade flows by domain / geography ---
    # Create a simple mapping from primary_domain to hardware_type relevance
    domain_hardware_map = {
        "GPU/AI Accelerator": ["GPU_High_End", "AI_Accelerator", "Advanced_Logic_Chip"],
        "CPU/Logic Chip": ["Advanced_Logic_Chip", "Consumer_Chip"],
        "Memory/DRAM": ["DRAM"],
        "Memory/NAND Flash": ["NAND_Flash"],
        "Foundry/Contract Manufacturing": ["Advanced_Logic_Chip", "Consumer_Chip", "DRAM", "NAND_Flash"],
        "Semiconductor Equipment": ["Advanced_DUV_Lithography"],
        "Chemical Materials": ["Chemical_Materials"],
        "Telecom Chip": ["Telecom_Chip", "5G_Baseband"],
        "Surveillance Chip": ["Surveillance_Chip"],
    }

    exposure_rows = []
    for _, row in companies.iterrows():
        company = row["company_name"]
        hq = row["hq_country_code"]
        domain = row["primary_domain"]
        year = row["year"]
        revenue = row["revenue_usd_bn"]
        relevant_hardware = domain_hardware_map.get(domain, [])

        if not relevant_hardware:
            continue

        # Exporter exposure (company's country exports relevant hardware)
        exp_flows = trade[
            (trade["exporter_country_code"] == hq)
            & (trade["hardware_type"].isin(relevant_hardware))
            & (trade["year"] == year)
        ]
        exp_value = exp_flows["trade_value_usd_millions"].sum()

        # Importer exposure (company's country imports relevant hardware)
        imp_flows = trade[
            (trade["importer_country_code"] == hq)
            & (trade["hardware_type"].isin(relevant_hardware))
            & (trade["year"] == year)
        ]
        imp_value = imp_flows["trade_value_usd_millions"].sum()

        exposure_rows.append(
            {
                "company_name": company,
                "year": year,
                "hq_country_code": hq,
                "primary_domain": domain,
                "revenue_usd_bn": revenue,
                "exporter_exposure_millions": exp_value,
                "importer_exposure_millions": imp_value,
                "total_exposure_millions": exp_value + imp_value,
                "relevant_hardware_types": ",".join(relevant_hardware),
            }
        )

    company_exposure = pd.DataFrame(exposure_rows)

    return {
        "country_profiles": country_profiles,
        "trade_network": trade_network,
        "company_exposure": company_exposure,
    }


@st.cache_data(show_spinner="Preparing simulation base state...")
def get_simulation_base_state(dfs: dict[str, pd.DataFrame]) -> dict:
    """Return latest-year baseline metrics per country for simulation."""
    macro = dfs["macro"]
    latest_year = macro["year"].max()
    baseline = macro[macro["year"] == latest_year][
        [
            "country_code",
            "country",
            "region",
            "ai_sovereignty_index",
            "geopolitical_risk_score",
            "gdp_usd_bn",
            "trade_balance_usd_bn",
            "semiconductor_exports_usd_bn",
        ]
    ].copy()

    # Merge latest energy data
    energy = dfs["energy"]
    energy_latest = energy[energy["year"] == latest_year][
        ["country_code", "ai_grid_stress_index", "energy_constraint_level", "pct_grid_used_by_ai"]
    ]
    baseline = baseline.merge(energy_latest, on="country_code", how="left")

    return {
        "latest_year": latest_year,
        "baseline_countries": baseline,
        "trade_flows": dfs["trade_flows"].copy(),
        "sanctions": dfs["sanctions"].copy(),
    }
