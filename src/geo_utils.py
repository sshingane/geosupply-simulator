"""Geographic utilities: country code mappings, lat/lon, ISO3 for Plotly."""
from typing import Dict, List, Tuple

import pandas as pd


# Mapping from dataset country codes to ISO 3166-1 alpha-3 (for Plotly choropleth)
COUNTRY_CODE_TO_ISO3: Dict[str, str] = {
    "AE": "ARE",  # United Arab Emirates
    "CN": "CHN",  # China
    "DE": "DEU",  # Germany
    "FR": "FRA",  # France
    "IN": "IND",  # India
    "IR": "IRN",  # Iran
    "JP": "JPN",  # Japan
    "KR": "KOR",  # South Korea
    "NL": "NLD",  # Netherlands
    "PK": "PAK",  # Pakistan
    "SA": "SAU",  # Saudi Arabia
    "TW": "TWN",  # Taiwan
    "US": "USA",  # United States
    "GB": "GBR",  # United Kingdom (if present)
    "RU": "RUS",  # Russia (if present)
    "IL": "ISR",  # Israel (if present)
    "TR": "TUR",  # Turkey (if present)
}

# Approximate lat/lon for map centroids (exporter/importer endpoints)
COUNTRY_CODE_TO_LATLON: Dict[str, Tuple[float, float]] = {
    "AE": (23.4241, 53.8478),
    "CN": (35.8617, 104.1954),
    "DE": (51.1657, 10.4515),
    "FR": (46.2276, 2.2137),
    "IN": (20.5937, 78.9629),
    "IR": (32.4279, 53.6880),
    "JP": (36.2048, 138.2529),
    "KR": (35.9078, 127.7669),
    "NL": (52.1326, 5.2913),
    "PK": (30.3753, 69.3451),
    "SA": (23.8859, 45.0792),
    "TW": (23.6978, 120.9605),
    "US": (37.0902, -95.7129),
    "GB": (55.3781, -3.4360),
    "RU": (61.5240, 105.3188),
    "IL": (31.0461, 34.8516),
    "TR": (38.9637, 35.2433),
}


def add_iso3(df: pd.DataFrame, country_code_col: str = "country_code") -> pd.DataFrame:
    """Add ISO3 column to a DataFrame based on country code."""
    df = df.copy()
    df["iso3"] = df[country_code_col].map(COUNTRY_CODE_TO_ISO3)
    return df


def get_latlon(country_code: str) -> Tuple[float, float]:
    """Return (lat, lon) for a country code."""
    return COUNTRY_CODE_TO_LATLON.get(country_code, (0.0, 0.0))


def add_latlon(df: pd.DataFrame, country_code_col: str) -> pd.DataFrame:
    """Add lat/lon columns to a DataFrame."""
    df = df.copy()
    lats, lons = [], []
    for code in df[country_code_col]:
        lat, lon = get_latlon(code)
        lats.append(lat)
        lons.append(lon)
    df["lat"] = lats
    df["lon"] = lons
    return df


def get_all_countries() -> List[str]:
    """Return list of all known country codes."""
    return list(COUNTRY_CODE_TO_ISO3.keys())


def get_region_color_map() -> Dict[str, str]:
    """Return a color map for regions."""
    return {
        "Asia-Pacific": "#1f77b4",
        "Europe": "#ff7f0e",
        "North America": "#2ca02c",
        "Middle East": "#d62728",
        "South Asia": "#9467bd",
        "Africa": "#8c564b",
        "South America": "#e377c2",
    }
