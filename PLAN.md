# GeoSupply AI Simulator — Implementation Plan

## Overview
A multi-page Streamlit web app combining geopolitical supply chain risk simulation, energy-AI nexus analysis, and stock impact forecasting for semiconductor hardware trade flows.

## Confirmed Decisions

| Decision | Choice |
|----------|--------|
| **Frontend** | Streamlit (multi-page) |
| **Maps** | Plotly choropleth + scattergeo route arrows |
| **Data Processing** | Pandas |
| **Network Analysis** | NetworkX (optional, for cascade effects) |
| **Stock Data** | yfinance |
| **Map View** | Full global view; auto-zoom to affected countries post-simulation |
| **SMIC Classification** | Public — ticker `0981.HK`, clearly labeled "Hong Kong only" |
| **Simulation Presets** | Yes — pre-built scenarios for one-click shock configuration |
| **Private Company Prediction** | Rule-based now; ML model reserved for Phase 6 |
| **Deployment** | Streamlit Cloud |

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | Streamlit (multi-page) | Native multi-page support, fastest build path, trivial deployment |
| Maps | Plotly (`choropleth` + `scattergeo` lines) | Built-in world geometry, curved arrows for trade routes, native Streamlit rendering |
| Data Processing | Pandas | Dataset is small (7,287 rows); no need for Spark/DuckDB |
| Network Analysis | NetworkX (optional) | For computing cascade effects through trade graph |
| Stock Data | yfinance | Free, covers all major public semiconductor companies |
| Styling | Streamlit native + custom CSS | Clean, professional look without heavy frontend work |
| Deployment | Streamlit Cloud | Free tier, GitHub integration, auto-deploy on push |

## Project Structure

```
geosupply-simulator/
├── .streamlit/
│   └── config.toml                 # Theme, page title, layout settings
├── data/
│   └── raw/                        # Your 6 CSVs (01-06)
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # Ingest + link all 6 tables
│   ├── geo_utils.py                # Country codes -> ISO3, lat/lon mappings
│   ├── simulation_engine.py        # Rule-based shock calculator + cascade logic
│   ├── stock_analyzer.py           # yfinance fetch + impact modeling (public + private)
│   └── viz.py                      # Reusable Plotly map/chart builders
├── pages/
│   ├── 1_🏠_Home.py                # Overview, methodology, quick-start buttons
│   ├── 2_🌍_Geopolitical_Simulator.py  # Configure shock -> see map + metrics
│   ├── 3_⚡_Energy_AI_Nexus.py     # Static dashboards with filters
│   ├── 4_📈_Stock_Impact.py        # Company exposure + shock -> stock estimate
│   └── 5_🔍_Data_Explorer.py      # Raw tables with synthetic/empirical filters
├── app.py                          # Entry point (redirects to Home)
├── requirements.txt
├── PLAN.md                         # This file
└── README.md
```

## Data Model

### Source Tables (from CSVs)
- `trade_flows` (5,657 rows, quarterly): exporter->importer flows by hardware type, trade value, geo-risk scores, route info
- `sanctions` (988 rows, event-level): sanctions by imposing/target country, restriction type, severity, estimated economic impact
- `budgets` (133 rows, annual, country-level): AI investment, subsidies, supercomputer projects, sovereignty index
- `energy` (133 rows, annual, country-level): grid capacity, AI datacenter energy use, renewable mix, carbon intensity
- `macro` (133 rows, annual, country-level): GDP, trade balance, tech sector % GDP, de-dollarization, sovereignty index
- `companies` (243 rows, annual, company-level): revenue, R&D, employees, geopolitical exposure

### Derived Tables (computed at load)
- `country_profiles`: merged budgets + energy + macro by country/year
- `trade_network`: graph edges (exporter->importer) with volume/value weights
- `company_exposure`: each company's revenue by geography and hardware type

## Phase-by-Phase Build

### Phase 1: Data Foundation
**Goal:** Load, clean, link, and cache all datasets.

**Tasks:**
- [ ] Copy 6 CSVs into `data/raw/`
- [ ] Build `src/data_loader.py`:
  - Load each CSV into a Pandas DataFrame
  - Standardize country codes across tables
  - Link tables on (country_code, year) and (exporter/importer, year_quarter)
  - Derive `country_profiles` by merging budgets + energy + macro
  - Derive `trade_network` as edge list with weights
  - Derive `company_exposure` by aggregating trade flows relevant to each company's domain
  - Cache everything with `@st.cache_data`
- [ ] Build `src/geo_utils.py`:
  - Map dataset country codes to ISO3 for Plotly
  - Map country codes to lat/lon for route drawing
  - Handle region groupings (Asia-Pacific, Europe, etc.)
- [ ] Write tests/validation: row counts, year ranges, null checks

**Success Criteria:** All 6 tables load in <2s; derived tables have correct join cardinality; no orphan rows.

---

### Phase 2: Simulation Engine
**Goal:** Build the rule-based shock calculator.

**Tasks:**
- [ ] Build `src/simulation_engine.py`:
  - Define `ShockConfig` dataclass: exporters[], hardware_types[], restriction_type, severity (1-5), duration (quarters)
  - Implement severity multipliers per restriction type:
    - Export Ban: 0.9, 0.7, 0.5, 0.3, 0.1
    - Tariff: 0.95, 0.85, 0.70, 0.50, 0.30
    - License Requirement: 0.90, 0.75, 0.55, 0.35, 0.15
    - Technology Transfer Ban: 0.95, 0.80, 0.60, 0.40, 0.20
  - Step 1 — Direct Impact: apply restriction_factor to affected trade_flows
  - Step 2 — Cascade Rerouting: for each affected importer, find alternative suppliers (same hardware, different exporter, lowest geo_risk_score); reroute up to 60% of lost volume
  - Step 3 — Country Metrics Update: adjust sovereignty_index and geo_risk_score based on supply loss
  - Step 4 — Energy Impact: for high AI-datacenter countries, reduce energy_demand_growth if chip availability drops
  - Support multiple simultaneous shocks (compound effects)
- [ ] Add pre-built scenario presets:
  - "Taiwan Strait Crisis" (TW export ban on Advanced Logic Chips, severity 4, 4 quarters)
  - "Full China Export Ban" (CN export ban on all hardware, severity 5, 8 quarters)
  - "CHIPS Act Acceleration" (US subsidies double, domestic capacity +40%, 8 quarters)
  - "EU Energy Constraint" (DE/NL grid stress -> datacenter moratorium, 4 quarters)
- [ ] Build `src/viz.py`: helper functions for Plotly choropleth baseline maps

**Success Criteria:** A single-shock scenario runs in <1s; multi-shock in <2s; output metrics are internally consistent.

**Implementation Notes:**
- Latest year only: `trade_flows` filtered to `year == year.max()` in `get_simulation_base_state()`.
- Rerouting: 60% cap preserved, but `trade_reduction` computed per disrupted route to avoid negative values on alternatives.
- Sovereignty: import-dependency-ratio based, capped 0–100.
- Exporter gain: scaled to customer dependency, max +5.0.

---

### Phase 3: Map Visualization
**Goal:** Build the interactive global map for the Simulator page.

**Tasks:**
- [ ] Implement `pages/2_🌍_Geopolitical_Simulator.py`:
  - Left sidebar: shock configuration UI (multiselects, sliders, "+ Add Shock", preset buttons)
  - Center: dynamic world map
    - Baseline choropleth: countries colored by `geo_risk_score`
    - Post-simulation: countries colored by `simulated_geo_risk_delta` (RdYlBu_r scale)
    - Trade route arrows: curved lines exporter->importer
      - Thickness proportional to trade_value
      - Color: blue (active), red (disrupted), pulsing animation for newly disrupted
    - Auto-zoom: compute bounding box of affected exporters/importers; animate zoom
    - Hover tooltips: country name, sovereignty index, geo-risk score, trade volume affected
  - Right panel: impact metrics
    - Before/after sovereignty index for top 10 affected countries (bar chart)
    - Estimated trade volume reduction ($B)
    - Energy grid stress changes for affected datacenter hubs
    - List of directly exposed companies
- [ ] Handle edge cases: no affected countries (empty state), all countries affected (global view), single-country zoom

**Success Criteria:** Map renders in <2s; zoom animation is smooth; tooltips show correct data; route colors update correctly post-simulation.

---

### Phase 4: Energy-AI Nexus
**Goal:** Build the static dashboard with filters.

**Tasks:**
- [ ] Implement `pages/3_⚡_Energy_AI_Nexus.py`:
  - Filters: country multiselect, year range slider
  - Scatter plot: `renewable_energy_pct` vs `pct_grid_used_by_ai`
    - Bubble size = total AI investment
    - Color = region
    - Hover: country, year, values
  - Time series line chart: AI datacenter energy TWh over time, per country
  - Warning table: countries where `ai_grid_stress_index > 0.5` or `energy_constraint_level == "High"`
  - Carbon analysis table: carbon_intensity_gco2_per_kwh per $B of AI investment
  - Download filtered data to CSV

**Success Criteria:** All charts render correctly; filters apply instantly; warning table highlights correct rows.

---

### Phase 5: Stock Impact Analysis
**Goal:** Integrate yfinance and build public + private company impact models.

**Tasks:**
- [ ] Build `src/stock_analyzer.py`:
  - Public companies (yfinance tickers):
    - NVDA, AMD, TSM, INTC, QCOM, MU, ASML, AMAT, LRCX, KLAC, Samsung (005930.KS), SK Hynix (000660.KS), Tokyo Electron (8035.T), MediaTek (2454.TW), SMIC (0981.HK)
    - Fetch 2015-2025 price history via yfinance (cache with `@st.cache_data`)
    - Compute revenue exposure to shocked trade flows by company domain
    - Analytical estimate: `revenue_hit / market_cap * sector_multiple`
    - Historical overlay: for real sanctions (`is_synthetic=0`), fetch actual stock movement around sanction date
    - Output: estimated % impact + confidence band + historical comparison sentence
  - Private companies (rule-based prediction):
    - Huawei HiSilicon, Biren, Cambricon, G42, Reliance Jio, STC
    - Compute revenue exposure to shocked trade flows
    - Find comparable public companies by domain + size
    - Apply comparable public company reaction, scaled by relative exposure
    - Adjust by country's `geopolitical_risk_score` trajectory
    - Output: predicted % impact with **"PREDICTED — NOT MARKET DATA"** watermark
- [ ] Implement `pages/4_📈_Stock_Impact.py`:
  - Tabs: "Publicly Traded" / "Private / Predicted"
  - Company selector (list with domain, HQ, revenue)
  - For public: stock price chart 2015-2025 with sanction event overlays
  - Shock input: run current simulation -> show impact for selected company
  - Display: analytical estimate, historical validation (if exists), confidence band
  - For private: predicted impact with clear watermark and methodology explanation

**Success Criteria:** yfinance data loads for all 15 public tickers; analytical estimates are directionally sensible; historical overlays match actual events; private predictions have clear disclaimers.

**Implementation Notes:**
- All 22 companies appear (exposed and unexposed). Zero-exposure companies show "No exposure" with methodology.
- Domain-hardware map expanded from 9 to 17 entries.
- Stock estimates stored as percentages (not decimals) to avoid 100× display inflation.
- Historical validation uses similarity score (0–100%) for closest sanction match.

---

### Phase 6: Polish + Deploy
**Goal:** Add presets, warnings, and deploy to Streamlit Cloud.

**Tasks:**
- [ ] Implement `pages/1_🏠_Home.py`:
  - App title, methodology explanation, data source disclaimers
  - Global toggle: show/hide synthetic data warnings
  - Quick-start buttons: "Run Taiwan Strait Scenario", "Explore Energy Nexus", "Check NVIDIA Exposure"
- [ ] Implement `pages/5_🔍_Data_Explorer.py`:
  - Raw table viewer for all 6 datasets
  - Filters: year, country, synthetic flag
  - Download to CSV button
  - Column-level data quality badge (green=empirical, yellow=synthetic)
- [ ] Add `.streamlit/config.toml`:
  - Page title: "GeoSupply AI Simulator"
  - Theme: dark or light (default dark for data viz)
  - Layout: wide
- [ ] Write `requirements.txt` with pinned versions
- [ ] Write `README.md` with setup instructions, methodology, data source credits
- [ ] Deploy to Streamlit Cloud:
  - Create GitHub repo
  - Push code
  - Connect to share.streamlit.io
  - Verify all pages load correctly

**Success Criteria:** App loads in <5s on first visit; all pages navigate correctly; presets work; synthetic warnings are visible; deployment URL is live and shareable.

**Implementation Notes:**
- Dashboard shows Gross/Rerouted/Net trade disruption metrics with tooltips.
- Python 3.14 f-string compatibility: pre-computed variables before f-string blocks; all lines in multi-line strings prefixed with `f`.
- NetworkX imported but cascade effects implemented via Pandas filters.
- Auto-zoom is instant (bounding box calculation) rather than animated.

---

## Post-Implementation Review

This section documents changes made during implementation that diverged from the original plan above.

### Phase 2: Simulation Engine — Implementation Changes

**Trade Flow Baseline:**
- Original plan used all historical trade flow data (2015–2025 cumulative, 5,657 rows).
- **Changed:** Filtered to latest year only (`year.max()`, 2025, 504 rows) in `get_simulation_base_state()`. Cumulative flows against single-year revenue inflated stock estimates ~8×.

**Rerouting Logic:**
- Original plan: reroute up to 60% of lost volume to alternative suppliers.
- **Changed:** Compute `trade_reduction` only on disrupted routes. The original implementation added rerouted volume to `new_trade_value` on alternative routes, causing `new_trade_value > baseline` and negative `trade_reduction`.

**New Metrics Tracked:**
- `gross_trade_disruption_millions`: total lost trade value before rerouting
- `rerouted_volume_millions`: trade value successfully redirected to alternatives
- `total_trade_reduction_millions` (net): `gross - rerouted`
- These replace the original single "Total Trade Reduction" metric.

**Sovereignty Scaling:**
- Original plan used hardcoded constants (0.5, 0.3, /10000) with no empirical basis.
- **Changed:** `import_dependency = disrupted_imports / total_imports` as the principled ratio. Sovereignty delta capped at 0–100; raw delta preserved in tooltip.
- Exporter sovereignty gain: `min(5.0, import_dependency * 10)` instead of flat +1.0.

### Phase 5: Stock Impact Analysis — Implementation Changes

**Company Coverage:**
- Original plan listed 15 public + 6 private companies. Dataset has 22 companies.
- **Changed:** All 22 companies shown including zero-exposure. Removed `trade_hit_millions > 0` filter.

**Domain-Hardware Map:**
- Original `domain_hardware_map` had 9 entries covering dataset domains.
- **Changed:** Expanded to 17 entries. Only 4 of 22 companies were appearing due to domain mismatches (18 skipped).

**Stock Percentage Display:**
- **Bug fixed:** `stock_estimate` was stored as decimal (0.32) while UI displayed "%", inflating percentages 100×. Engine now multiplies by 100 before returning.

**Historical Validation:**
- Implemented similarity scoring (0–100%) for closest historical sanction match, not just date-based lookup.

### Phase 6: Polish + Deploy — Implementation Changes

**Dashboard Metrics:**
- Simulator page shows 3 trade metrics (Gross, Rerouted, Net) with hover tooltips explaining methodology.

**Python 3.14 Compatibility:**
- Fixed f-string syntax errors where `}` appeared inside f-string expression fields (Python 3.14 parser is stricter).
- Fixed multi-line `st.info()` strings where only the first line had an `f` prefix.

---

### Phase 7 (Future): ML Prediction Layer
**Status:** Deferred. Rule-based comparable scaling is sufficient for MVP.

**Goal:** Replace rule-based private company prediction with a learned model.

**Approach:**
- Train a k-NN or small random forest regressor on public companies:
  - Features: revenue, R&D, employees, geopolitical_exposure, sanction_risk_flag, domain, country_risk_score
  - Target: actual stock return 30/60/90 days post-sanction
- For private companies, use the model to predict impact based on feature similarity to public comps
- Validate: leave-one-public-company-out cross-validation
- Trigger: implement only if private company predictions consistently diverge from actual outcomes by >50%, or if public company historical data yields a model with R^2 > 0.3

**Current Replacement:**
- Private companies use rule-based comparable scaling: find public companies by domain + revenue size, apply mean reaction scaled by relative exposure, adjusted by country risk trajectory.

---

## Pre-Built Simulation Scenarios

### 1. Taiwan Strait Crisis
- **Shocks:** TW export ban on Advanced Logic Chips, severity 4, 4 quarters
- **Affected:** US, CN, EU (major importers of TW chips)
- **Expected outcome:** Sovereignty drops for dependent countries; TSMC stock hit; Intel/ Samsung gain as alternative suppliers

**Before/After Fix:**

| Metric | Original (Broken) | Fixed |
|--------|------------------|-------|
| Gross Disruption | ~$162B (all years cumulative) | ~$14B (latest year only) |
| Rerouted Volume | N/A (negative values) | ~$5.3B |
| Net Disruption | ~$21B | ~$9B |
| MediaTek Stock | 1313% | 175% |
| AMD Stock | 201% | 31% |
| TSMC Stock | 250% | 33% |

### 2. Full China Export Ban
- **Shocks:** CN export ban on all hardware types, severity 5, 8 quarters
- **Affected:** Global (CN is major exporter of consumer chips, chemicals, components)
- **Expected outcome:** Massive supply shock; SMIC predicted impact (private); ASEAN countries gain rerouted volume

### 3. CHIPS Act Acceleration
- **Shocks:** US subsidies double, domestic capacity +40%, 8 quarters
- **Affected:** US sovereignty increases; TSMC/TW share of US market declines
- **Expected outcome:** Intel, Applied Materials, Lam Research stock boost; US energy grid stress increases

### 4. EU Energy Constraint
- **Shocks:** DE/NL grid stress -> datacenter moratorium, severity 3, 4 quarters
- **Affected:** EU AI buildout slows; cloud providers (AWS/Azure/GCP EU regions) constrained
- **Expected outcome:** Sovereignty drops for EU; carbon intensity improves; investment shifts to US/Asia

---

## Map Behavior Specification

### Default State
- Full global view
- Choropleth: countries colored by baseline `geo_risk_score`
- No route lines visible (or faint background routes)

### Post-Simulation State
- Auto-zoom animation to bounding box of affected exporters + importers
- Choropleth update: `simulated_geo_risk_delta` (new score - baseline)
- Route lines appear:
  - Blue: active, unaffected routes
  - Red: disrupted routes (thickness = lost trade value)
  - Pulsing animation on newly disrupted routes
- Hover tooltips:
  - Country: name, baseline sovereignty, new sovereignty, delta
  - Route: exporter, importer, hardware type, baseline value, new value, % reduction

### Technical Implementation
```python
# Choropleth baseline
fig = px.choropleth(
    df_countries,
    locations="iso3",
    color="geo_risk_score",
    color_continuous_scale="RdYlBu_r",
    scope="world"
)

# Route arrows
fig.add_trace(go.Scattergeo(
    lon=[exporter_lon, importer_lon, None],  # None breaks line for next segment
    lat=[exporter_lat, importer_lat, None],
    mode='lines',
    line=dict(width=value/100, color='red' if disrupted else 'blue'),
    opacity=0.6
))

# Auto-zoom
lons = affected_countries['lon'].tolist()
lats = affected_countries['lat'].tolist()
fig.update_geos(
    lonaxis_range=[min(lons)-10, max(lons)+10],
    lataxis_range=[min(lats)-10, max(lats)+10]
)
```

---

## Stock Impact Methodology

### Public Companies (Analytical + Historical)

**Step 1: Revenue Exposure**
```
exposure = sum(trade_flow_value WHERE importer_relevant_to_company_domain)
revenue_hit = exposure * restriction_factor * company_market_share_in_domain
```

**Step 2: Analytical Estimate**
```
revenue_impact_pct = revenue_hit / company_annual_revenue
stock_impact_estimate = revenue_impact_pct * sector_revenue_multiple
# sector_revenue_multiple ~= 3-5 for semiconductors (empirical)
```

**Step 3: Historical Validation**
```
For each real sanction (is_synthetic=0) affecting this company:
  actual_return_30d = price[date+30] / price[date] - 1
  predicted_return = model(sanction_severity, company_exposure)
  display: "In [date], a similar [restriction_type] caused [actual_return_30d]%. Our model estimates [predicted_return]%."
```

### Private Companies (Rule-Based Prediction)

**Step 1: Find Comparable Public Companies**
```
comparables = filter(public_companies WHERE domain == target_domain AND revenue_within_2x)
```

**Step 2: Scale Public Reaction**
```
base_reaction = mean(comparable.actual_stock_return_for_similar_shock)
scale_factor = target_revenue_exposure / mean(comparable.revenue_exposure)
predicted_impact = base_reaction * scale_factor
```

**Step 3: Adjust for Country Risk Trajectory**
```
risk_adjustment = (target_country_geo_risk_new - target_country_geo_risk_baseline) / 10
final_prediction = predicted_impact * (1 + risk_adjustment)
```

**Output:**
- Predicted % impact
- Confidence: LOW
- Watermark: "PREDICTED — NOT MARKET DATA"
- Comparable companies used
- Methodology expandable section

---

## Bug Log

| # | Phase | Severity | Bug | Root Cause | Fix |
|---|-------|----------|-----|-----------|-----|
| 1 | Phase 5 | Critical | Stock Impact page `SyntaxError` | Python 3.14 f-string parser rejected `}"` inside format field | Pre-computed strings before f-string block |
| 2 | Phase 2 | Critical | Stock estimates inflated ~8× | Simulation used cumulative 10-year trade data against 1-year revenue | Filter `trade_flows` to latest year only |
| 3 | Phase 2 | Critical | Rerouting created negative `trade_reduction` | Code added rerouted volume to `new_trade_value` on alternatives | Compute `trade_reduction` only on disrupted routes |
| 4 | Phase 1 | Critical | Only 4 of 22 companies appeared | `domain_hardware_map` covered 9 domains; dataset has 15+ | Expanded map to 17 entries |
| 5 | Phase 2 | Medium | Zero-exposure companies hidden | `company_impacts_df` filtered with `trade_hit > 0` | Removed filter |
| 6 | Phase 2 | Medium | Stock percentages off by 100× | `stock_estimate` stored as decimal while UI showed "%" | Multiply by 100 in engine |
| 7 | Phase 5 | Medium | No-exposure messages showed raw Python | Multi-line string: only first line had `f` prefix | Added `f` prefix to all lines |
| 8 | Phase 1 | Low | Company exposure deduplicated too aggressively | `drop_duplicates` removed all but latest year | Restored to keep all years |

## Deployment Checklist

- [x] GitHub repo created
- [x] All code committed
- [x] `requirements.txt` tested in clean venv
- [x] `.streamlit/config.toml` configured
- [x] Data files included in repo
- [x] Streamlit Cloud account connected
- [x] App deployed and URL tested
- [x] All 5 pages load correctly
- [x] Preset scenarios run without errors
- [x] Synthetic data warnings visible
- [x] README.md complete
- [ ] Phase 7 (ML) — deferred to future work
- [ ] NetworkX graph analysis — not used (cascade effects implemented via Pandas)

## Deployment URL (Target)
`https://geosupply-simulator.streamlit.app` (or similar, depending on availability)

---

## Notes
- All synthetic data (`is_synthetic=1`) must be clearly labeled in visualizations
- The app should work offline if data is cached; yfinance requires internet
- Performance target: first page load <5s, simulation run <2s, map re-render <2s
- Accessibility: all charts should have alt-text or titles; colorblind-friendly palettes
