"""Rule-based geopolitical shock simulation engine."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class ShockConfig:
    """Configuration for a single geopolitical shock."""
    exporters: List[str]  # country codes
    hardware_types: List[str]
    restriction_type: str  # Export_Ban, Tariff, License_Requirement, Technology_Transfer_Ban
    severity: int  # 1-5
    duration_quarters: int


# Severity multiplier matrices by restriction type
# Values represent remaining trade capacity (1.0 = no restriction, 0.0 = full ban)
SEVERITY_MULTIPLIERS = {
    "Export_Ban": [1.0, 0.9, 0.7, 0.5, 0.3, 0.1],
    "Tariff": [1.0, 0.95, 0.85, 0.70, 0.50, 0.30],
    "License_Requirement": [1.0, 0.90, 0.75, 0.55, 0.35, 0.15],
    "Technology_Transfer_Ban": [1.0, 0.95, 0.80, 0.60, 0.40, 0.20],
}

# Default fallback if restriction type not found
_DEFAULT_MULTIPLIERS = [1.0, 0.95, 0.85, 0.70, 0.50, 0.30]


def _get_multiplier(restriction_type: str, severity: int) -> float:
    """Get trade capacity multiplier for a restriction type and severity."""
    mults = SEVERITY_MULTIPLIERS.get(restriction_type, _DEFAULT_MULTIPLIERS)
    idx = max(0, min(severity, len(mults) - 1))
    return mults[idx]


@dataclass
class SimulationResult:
    """Results from running a simulation."""
    shocked_countries: pd.DataFrame
    trade_impacts: pd.DataFrame
    energy_impacts: pd.DataFrame
    company_impacts: pd.DataFrame
    total_trade_reduction_millions: float  # Net disruption
    gross_trade_disruption_millions: float  # Gross disruption before rerouting
    rerouted_volume_millions: float  # Volume successfully rerouted
    affected_exporter_countries: List[str]
    affected_importer_countries: List[str]


def run_simulation(
    shocks: List[ShockConfig],
    trade_flows: pd.DataFrame,
    country_baseline: pd.DataFrame,
    energy_data: pd.DataFrame,
    company_exposure: pd.DataFrame,
    max_reroute_pct: float = 0.60,
) -> SimulationResult:
    """Run a multi-shock simulation and return impacts."""
    trade = trade_flows.copy()
    baseline = country_baseline.copy()

    # Track which routes are directly shocked
    trade["shock_multiplier"] = 1.0
    trade["is_disrupted"] = False

    affected_exporters = set()
    affected_importers = set()

    for shock in shocks:
        mask = (
            trade["exporter_country_code"].isin(shock.exporters)
            & trade["hardware_type"].isin(shock.hardware_types)
        )
        if mask.any():
            mult = _get_multiplier(shock.restriction_type, shock.severity)
            trade.loc[mask, "shock_multiplier"] *= mult
            trade.loc[mask, "is_disrupted"] = True
            affected_exporters.update(shock.exporters)
            affected_importers.update(trade.loc[mask, "importer_country_code"].unique().tolist())

    # Compute trade reduction on DISRUPTED routes only
    trade["trade_reduction"] = 0.0
    trade.loc[trade["is_disrupted"], "trade_reduction"] = (
        trade.loc[trade["is_disrupted"], "trade_value_usd_millions"]
        * (1 - trade.loc[trade["is_disrupted"], "shock_multiplier"])
    )

    gross_disruption = trade["trade_reduction"].sum()
    total_rerouted = 0.0

    # --- Cascade Rerouting ---
    # For each affected importer, try to find alternative suppliers
    for importer in affected_importers:
        imp_mask = trade["importer_country_code"] == importer
        disrupted = trade[imp_mask & trade["is_disrupted"]].copy()

        for _, row in disrupted.iterrows():
            hw = row["hardware_type"]
            lost_value = row["trade_reduction"]
            if lost_value <= 0:
                continue

            # Find alternative exporters for same hardware, excluding original
            alt_mask = (
                (trade["importer_country_code"] == importer)
                & (trade["hardware_type"] == hw)
                & (~trade["exporter_country_code"].isin([row["exporter_country_code"]]))
                & (~trade["is_disrupted"])
            )
            alts = trade[alt_mask].copy()
            if alts.empty:
                continue

            # Prefer lowest geo-risk score
            alts = alts.sort_values("geo_risk_score_exporter")
            reroute_capacity = lost_value * max_reroute_pct
            rerouted = 0.0

            for idx, alt in alts.iterrows():
                available = alt["trade_value_usd_millions"] * 0.3  # assume 30% spare capacity
                take = min(available, reroute_capacity - rerouted)
                if take > 0:
                    rerouted += take
                if rerouted >= reroute_capacity:
                    break

            # Reduce the original disruption due to rerouting
            if rerouted > 0:
                orig_idx = row.name
                trade.at[orig_idx, "trade_reduction"] -= rerouted
                total_rerouted += rerouted

    # Recalculate net total after rerouting
    net_disruption = trade["trade_reduction"].sum()

    # --- Country Impact Aggregation ---
    country_impacts = []
    for _, row in baseline.iterrows():
        cc = row["country_code"]

        # Exporter impact
        exp_mask = trade["exporter_country_code"] == cc
        exp_loss = trade.loc[exp_mask, "trade_reduction"].sum()
        exp_baseline = trade.loc[exp_mask, "trade_value_usd_millions"].sum()

        # Importer impact
        imp_mask = trade["importer_country_code"] == cc
        imp_loss = trade.loc[imp_mask, "trade_reduction"].sum()
        imp_baseline = trade.loc[imp_mask, "trade_value_usd_millions"].sum()

        # Import dependency ratio (fraction of imports disrupted)
        total_imports = imp_baseline
        if total_imports > 0:
            import_dependency = imp_loss / total_imports
        else:
            import_dependency = 0.0

        # Sovereignty impact: based on import dependency
        sov_delta = -import_dependency * 20  # 100% loss -> -20 points

        # Exporters gain sovereignty proportional to customer dependency
        if cc in affected_exporters:
            sov_delta += min(5.0, import_dependency * 10)

        # Apply and cap
        new_sov_raw = row["ai_sovereignty_index"] + sov_delta
        new_sov = max(0.0, min(100.0, new_sov_raw))

        # Geo-risk: based on import dependency
        geo_delta = import_dependency * 10  # 100% loss -> +10 points
        new_geo = row["geopolitical_risk_score"] + geo_delta

        country_impacts.append(
            {
                "country_code": cc,
                "country": row["country"],
                "region": row.get("region", ""),
                "baseline_sovereignty": row["ai_sovereignty_index"],
                "new_sovereignty": new_sov,
                "sovereignty_delta": sov_delta,
                "sovereignty_raw": new_sov_raw,
                "baseline_geo_risk": row["geopolitical_risk_score"],
                "new_geo_risk": new_geo,
                "geo_risk_delta": geo_delta,
                "exporter_loss_millions": exp_loss,
                "importer_loss_millions": imp_loss,
                "total_trade_baseline_millions": exp_baseline + imp_baseline,
                "import_dependency": import_dependency,
            }
        )

    shocked_countries = pd.DataFrame(country_impacts)

    # --- Energy Impact ---
    energy_impacts = []
    latest_energy = energy_data[energy_data["year"] == energy_data["year"].max()]
    for _, row in latest_energy.iterrows():
        cc = row["country_code"]
        country_row = shocked_countries[shocked_countries["country_code"] == cc]
        if country_row.empty:
            continue
        import_dependency = country_row.iloc[0]["import_dependency"]

        # If a country loses chip supply, AI buildout slows -> energy demand growth decreases
        energy_delta = -import_dependency * row["pct_grid_used_by_ai"] / 10
        new_stress = max(0.0, row["ai_grid_stress_index"] + energy_delta)

        energy_impacts.append(
            {
                "country_code": cc,
                "country": row["country"],
                "baseline_grid_stress": row["ai_grid_stress_index"],
                "new_grid_stress": new_stress,
                "grid_stress_delta": new_stress - row["ai_grid_stress_index"],
                "baseline_pct_grid_ai": row["pct_grid_used_by_ai"],
                "energy_constraint_level": row["energy_constraint_level"],
                "import_dependency": import_dependency,
            }
        )
    energy_impacts_df = pd.DataFrame(energy_impacts)

    # --- Company Impact ---
    company_impacts = []
    for _, row in company_exposure.iterrows():
        company = row["company_name"]
        hq = row["hq_country_code"]
        domain = row["primary_domain"]
        revenue = row["revenue_usd_bn"]
        relevant_hw = row["relevant_hardware_types"].split(",")

        # Find shocked trade flows relevant to this company
        exp_mask = (
            (trade["exporter_country_code"] == hq)
            & (trade["hardware_type"].isin(relevant_hw))
            & (trade["is_disrupted"])
        )
        imp_mask = (
            (trade["importer_country_code"] == hq)
            & (trade["hardware_type"].isin(relevant_hw))
            & (trade["is_disrupted"])
        )

        exp_hit = trade.loc[exp_mask, "trade_reduction"].sum() if exp_mask.any() else 0
        imp_hit = trade.loc[imp_mask, "trade_reduction"].sum() if imp_mask.any() else 0
        total_hit = exp_hit + imp_hit

        if total_hit > 0 and revenue > 0:
            revenue_impact_pct = (total_hit / 1000) / revenue
            stock_estimate = revenue_impact_pct * 4.0 * 100  # sector multiple ~4x, convert to pct
        else:
            revenue_impact_pct = 0.0
            stock_estimate = 0.0

        company_impacts.append(
            {
                "company_name": company,
                "hq_country_code": hq,
                "primary_domain": domain,
                "revenue_usd_bn": revenue,
                "trade_hit_millions": total_hit,
                "revenue_impact_pct": revenue_impact_pct,
                "estimated_stock_impact_pct": stock_estimate,
            }
        )

    company_impacts_df = pd.DataFrame(company_impacts)
    # Keep all companies, including those with zero trade exposure

    # Trade impact detail table (disrupted routes only)
    trade_impacts = trade[trade["is_disrupted"]].copy()
    trade_impacts = trade_impacts[
        [
            "exporter_country_code",
            "exporter_country",
            "importer_country_code",
            "importer_country",
            "hardware_type",
            "trade_value_usd_millions",
            "trade_reduction",
            "trade_route",
        ]
    ].copy()

    return SimulationResult(
        shocked_countries=shocked_countries,
        trade_impacts=trade_impacts,
        energy_impacts=energy_impacts_df,
        company_impacts=company_impacts_df,
        total_trade_reduction_millions=net_disruption,
        gross_trade_disruption_millions=gross_disruption,
        rerouted_volume_millions=total_rerouted,
        affected_exporter_countries=sorted(list(affected_exporters)),
        affected_importer_countries=sorted(list(affected_importers)),
    )


# --- Pre-built scenarios ---

def scenario_taiwan_strait_crisis() -> List[ShockConfig]:
    return [
        ShockConfig(
            exporters=["TW"],
            hardware_types=["Advanced_Logic_Chip"],
            restriction_type="Export_Ban",
            severity=4,
            duration_quarters=4,
        )
    ]


def scenario_full_china_export_ban() -> List[ShockConfig]:
    return [
        ShockConfig(
            exporters=["CN"],
            hardware_types=["Advanced_Logic_Chip", "Consumer_Chip", "DRAM", "NAND_Flash", "AI_Accelerator", "GPU_High_End", "Telecom_Chip", "Surveillance_Chip", "Chemical_Materials"],
            restriction_type="Export_Ban",
            severity=5,
            duration_quarters=8,
        )
    ]


def scenario_chips_act_acceleration() -> List[ShockConfig]:
    # Modeled as US domestic capacity surge -> reduced imports from others
    return [
        ShockConfig(
            exporters=["TW", "KR", "JP"],
            hardware_types=["Advanced_Logic_Chip", "DRAM", "NAND_Flash"],
            restriction_type="Tariff",
            severity=3,
            duration_quarters=8,
        )
    ]


def scenario_eu_energy_constraint() -> List[ShockConfig]:
    return [
        ShockConfig(
            exporters=["DE", "NL"],
            hardware_types=["AI_Accelerator", "GPU_High_End", "Advanced_Logic_Chip"],
            restriction_type="License_Requirement",
            severity=3,
            duration_quarters=4,
        )
    ]
