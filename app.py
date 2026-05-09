import streamlit as st

st.set_page_config(
    page_title="GeoSupply AI Simulator",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🌍 GeoSupply AI Simulator")
st.markdown(
    """
    **Analyze geopolitical shocks to the global AI hardware supply chain.**

    This app combines trade flow data, energy grids, and company exposure to simulate
    how geopolitical events reshape the semiconductor landscape.
    """
)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🎮 Simulator")
    st.write("Configure geopolitical shocks and visualize global trade disruptions.")
    if st.button("Launch Simulator", use_container_width=True):
        st.switch_page("pages/2_🌍_Geopolitical_Simulator.py")

with col2:
    st.subheader("⚡ Energy Nexus")
    st.write("Explore datacenter energy constraints and carbon intensity.")
    if st.button("Explore Energy", use_container_width=True):
        st.switch_page("pages/3_⚡_Energy_AI_Nexus.py")

with col3:
    st.subheader("📈 Stock Impact")
    st.write("Analyze public and private company exposure to supply shocks.")
    if st.button("Check Stocks", use_container_width=True):
        st.switch_page("pages/4_📈_Stock_Impact.py")

st.divider()

st.subheader("Quick Start Scenarios")
scenario = st.selectbox(
    "Choose a pre-built scenario to run:",
    [
        "Select a scenario...",
        "Taiwan Strait Crisis",
        "Full China Export Ban",
        "CHIPS Act Acceleration",
        "EU Energy Constraint",
    ],
)

if scenario != "Select a scenario...":
    st.info(f"Go to the **Geopolitical Simulator** page to run the '{scenario}' scenario.")

st.divider()

st.subheader("Data Sources & Methodology")
st.markdown(
    """
    - **Trade Flows:** Quarterly semiconductor trade by country, hardware type, and value (2015–2025)
    - **Sanctions:** Export controls, tariffs, and technology transfer bans (2015–2025)
    - **Budgets:** National AI infrastructure investments and subsidies
    - **Energy:** Grid capacity, AI datacenter energy consumption, renewable mix
    - **Macro:** GDP, trade balance, tech sector share, sovereignty indices
    - **Companies:** Revenue, R&D, employees, and geopolitical exposure for 22 firms

    **Synthetic Data Warning:** Some rows in the dataset are estimated or pattern-based
    (`is_synthetic = 1`). These are clearly labeled throughout the app.
    """
)

with st.expander("Simulation Methodology"):
    st.markdown(
        """
        1. **Direct Impact:** Apply restriction multipliers based on sanction type and severity.
        2. **Cascade Rerouting:** Affected importers seek alternative suppliers (up to 60% rerouting).
        3. **Country Metrics:** Adjust sovereignty index and geopolitical risk scores.
        4. **Energy Impact:** Reduce grid stress if chip shortages slow datacenter buildout.
        5. **Stock Impact:** Estimate revenue hits and map to historical market reactions.
        """
    )
