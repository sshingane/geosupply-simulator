"""Stock data fetching and impact modeling."""
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# yfinance is optional; gracefully degrade if not installed
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


# Public company tickers mapped from dataset names
PUBLIC_TICKERS: Dict[str, str] = {
    "NVIDIA": "NVDA",
    "AMD": "AMD",
    "TSMC": "TSM",
    "Intel": "INTC",
    "Qualcomm": "QCOM",
    "Micron Technology": "MU",
    "ASML": "ASML",
    "Applied Materials": "AMAT",
    "Lam Research": "LRCX",
    "KLA Corporation": "KLAC",
    "Samsung": "005930.KS",
    "SK Hynix": "000660.KS",
    "Tokyo Electron": "8035.T",
    "MediaTek": "2454.TW",
    "SMIC": "0981.HK",
}

PRIVATE_COMPANIES = [
    "Huawei HiSilicon",
    "Biren Technology",
    "Cambricon",
    "G42",
    "Reliance Jio",
    "STC",
]


@st.cache_data(show_spinner="Fetching stock data...", ttl=3600)
def fetch_stock_history(ticker: str, start: str = "2015-01-01", end: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Fetch historical stock prices from Yahoo Finance."""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        if data.empty:
            return None
        # Flatten multi-index columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        return data
    except Exception:
        return None


@st.cache_data(show_spinner="Fetching all stock histories...")
def fetch_all_stock_histories() -> Dict[str, pd.DataFrame]:
    """Fetch histories for all public companies."""
    results = {}
    for company, ticker in PUBLIC_TICKERS.items():
        df = fetch_stock_history(ticker)
        if df is not None:
            results[company] = df
    return results


def get_company_market_cap(ticker: str) -> Optional[float]:
    """Get latest market cap in USD billions."""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        info = yf.Ticker(ticker).info
        mc = info.get("marketCap")
        if mc:
            return mc / 1e9
        return None
    except Exception:
        return None


def get_all_market_caps() -> Dict[str, Optional[float]]:
    """Get market caps for all public companies."""
    return {company: get_company_market_cap(ticker) for company, ticker in PUBLIC_TICKERS.items()}


def compute_historical_sanction_impact(
    company: str,
    sanction_date: pd.Timestamp,
    stock_df: pd.DataFrame,
    window_days: int = 30,
) -> Optional[float]:
    """Compute stock return around a sanction date."""
    if stock_df is None or stock_df.empty:
        return None
    if "Date" not in stock_df.columns and "date" not in stock_df.columns:
        return None

    date_col = "Date" if "Date" in stock_df.columns else "date"
    stock_df = stock_df.copy()
    stock_df[date_col] = pd.to_datetime(stock_df[date_col])

    before = stock_df[stock_df[date_col] <= sanction_date]
    after = stock_df[stock_df[date_col] >= sanction_date]

    if before.empty or after.empty:
        return None

    price_before = before.iloc[-1]["Close"]
    # Find price window_days after
    target_date = sanction_date + pd.Timedelta(days=window_days)
    after_window = after[after[date_col] <= target_date]
    if after_window.empty:
        return None
    price_after = after_window.iloc[-1]["Close"]

    return (price_after / price_before - 1) * 100


def find_historical_comparables(
    target_domain: str,
    target_revenue: float,
    company_exposure: pd.DataFrame,
    stock_histories: Dict[str, pd.DataFrame],
    sanctions: pd.DataFrame,
) -> List[Dict]:
    """Find comparable public companies for a private company prediction."""
    # Map domain to comparable public companies
    domain_map = {
        "GPU/AI Accelerator": ["NVIDIA", "AMD"],
        "CPU/Logic Chip": ["Intel", "AMD"],
        "Memory/DRAM": ["Micron Technology", "Samsung", "SK Hynix"],
        "Memory/NAND Flash": ["Samsung", "SK Hynix"],
        "Foundry/Contract Manufacturing": ["TSMC", "SMIC", "Intel"],
        "Semiconductor Equipment": ["ASML", "Applied Materials", "Lam Research", "KLA Corporation", "Tokyo Electron"],
        "Chemical Materials": ["Tokyo Electron"],
        "Telecom Chip": ["Qualcomm", "MediaTek"],
        "Surveillance Chip": ["NVIDIA"],
    }

    comparables = domain_map.get(target_domain, [])
    results = []

    for comp in comparables:
        if comp not in stock_histories:
            continue
        comp_row = company_exposure[company_exposure["company_name"] == comp]
        if comp_row.empty:
            continue
        comp_revenue = comp_row.iloc[0]["revenue_usd_bn"]
        comp_exposure = comp_row.iloc[0]["total_exposure_millions"]

        # Find historical sanction impacts for this company
        comp_sanctions = sanctions[
            (sanctions["target_country_code"].isin([comp_row.iloc[0]["hq_country_code"]]))
            & (sanctions["is_synthetic"] == 0)
        ]
        impacts = []
        for _, s in comp_sanctions.iterrows():
            impact = compute_historical_sanction_impact(
                comp, pd.to_datetime(s["date_implemented"]), stock_histories[comp]
            )
            if impact is not None:
                impacts.append(impact)

        avg_impact = sum(impacts) / len(impacts) if impacts else 0.0

        results.append(
            {
                "company": comp,
                "revenue": comp_revenue,
                "exposure": comp_exposure,
                "avg_historical_impact_pct": avg_impact,
                "scale_factor": target_revenue / comp_revenue if comp_revenue > 0 else 1.0,
            }
        )

    return results


def predict_private_company_impact(
    company_name: str,
    domain: str,
    revenue: float,
    hq_country_code: str,
    trade_hit_millions: float,
    country_geo_risk_delta: float,
    company_exposure: pd.DataFrame,
    stock_histories: Dict[str, pd.DataFrame],
    sanctions: pd.DataFrame,
) -> Dict:
    """Predict stock impact for a private company using rule-based comparable scaling."""
    comparables = find_historical_comparables(
        domain, revenue, company_exposure, stock_histories, sanctions
    )

    if not comparables:
        # Fallback: purely analytical
        revenue_impact_pct = (trade_hit_millions / 1000) / revenue if revenue > 0 else 0
        predicted = revenue_impact_pct * 4.0 * (1 + country_geo_risk_delta / 10)
        return {
            "predicted_impact_pct": predicted,
            "method": "analytical_fallback",
            "comparables_used": [],
            "confidence": "LOW",
        }

    # Weighted average of comparable reactions, scaled by revenue and exposure
    weighted_sum = 0.0
    weight_sum = 0.0
    comps_used = []

    for comp in comparables:
        weight = 1.0 / (abs(comp["revenue"] - revenue) + 1.0)  # closer revenue = higher weight
        scaled_impact = comp["avg_historical_impact_pct"] * comp["scale_factor"]
        weighted_sum += scaled_impact * weight
        weight_sum += weight
        comps_used.append(comp["company"])

    base_prediction = weighted_sum / weight_sum if weight_sum > 0 else 0.0

    # Adjust for country geo-risk trajectory
    risk_adjustment = 1 + (country_geo_risk_delta / 10)
    final_prediction = base_prediction * risk_adjustment

    return {
        "predicted_impact_pct": final_prediction,
        "method": "comparable_scaling",
        "comparables_used": comps_used,
        "confidence": "LOW",
    }


def _sanction_similarity_score(
    sanction_row: pd.Series,
    restriction_type: str,
    target_countries: List[str],
    hardware_types: List[str],
) -> float:
    """Compute a 0-100 similarity score between a historical sanction and current shock."""
    score = 0.0

    # Restriction type match (40 points)
    if sanction_row.get("restriction_type") == restriction_type:
        score += 40.0
    elif restriction_type in str(sanction_row.get("restriction_type", "")):
        score += 20.0

    # Target country match (30 points)
    target = sanction_row.get("target_country_code", "")
    if target in target_countries:
        score += 30.0
    elif sanction_row.get("imposing_country_code") in target_countries:
        score += 15.0

    # Technology overlap (30 points)
    affected_tech = str(sanction_row.get("affected_technology", ""))
    tech_match = any(hw in affected_tech for hw in hardware_types)
    if tech_match:
        score += 30.0
    elif any(hw.lower() in affected_tech.lower() for hw in hardware_types):
        score += 15.0

    return score


def find_closest_historical_sanction(
    sanctions: pd.DataFrame,
    restriction_type: str,
    target_countries: List[str],
    hardware_types: List[str],
    company_name: str,
    stock_histories: Dict[str, pd.DataFrame],
    min_similarity: float = 30.0,
) -> Optional[Dict]:
    """Find the closest real historical sanction and compute actual stock impact."""
    real_sanctions = sanctions[sanctions["is_synthetic"] == 0].copy()
    if real_sanctions.empty:
        return None

    # Score each sanction
    real_sanctions["similarity_score"] = real_sanctions.apply(
        lambda row: _sanction_similarity_score(row, restriction_type, target_countries, hardware_types),
        axis=1,
    )

    best = real_sanctions.nlargest(1, "similarity_score").iloc[0]
    if best["similarity_score"] < min_similarity:
        return None

    # Compute actual stock impact for this company
    sanction_date = pd.to_datetime(best["date_implemented"])
    stock_df = stock_histories.get(company_name)
    actual_impact = compute_historical_sanction_impact(
        company_name, sanction_date, stock_df, window_days=90
    )

    # Compute what our model would have estimated for this historical event
    # Use severity as proxy
    historical_severity = best.get("severity_level", 3)
    historical_restriction = best.get("restriction_type", restriction_type)
    # Simple analytical estimate
    estimated_for_historical = -historical_severity * 2.5  # rough heuristic

    return {
        "date": best["date_implemented"],
        "imposing_country": best.get("imposing_country", "Unknown"),
        "target_country": best.get("target_country", "Unknown"),
        "restriction_type": best.get("restriction_type", "Unknown"),
        "affected_technology": best.get("affected_technology", "Unknown"),
        "severity": historical_severity,
        "similarity_score": best["similarity_score"],
        "actual_impact_pct": actual_impact,
        "estimated_for_historical_pct": estimated_for_historical,
        "description": best.get("description", ""),
    }
