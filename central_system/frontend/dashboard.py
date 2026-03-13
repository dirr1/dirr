import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Polymarket Central Intelligence", layout="wide")

API_URL = "http://localhost:8000"

st.title("🏛️ Polymarket Central Intelligence Dashboard")
st.markdown("---")

# Sidebar Stats
try:
    stats_res = requests.get(f"{API_URL}/stats", timeout=2)
    if stats_res.status_code == 200:
        stats = stats_res.json()
        st.sidebar.metric("Trades Analyzed", stats.get("total_trades_analyzed", 0))
        st.sidebar.metric("Wallets Tracked", stats.get("unique_wallets_tracked", 0))
    else:
        st.sidebar.warning(f"API Error: {stats_res.status_code}")
except:
    st.sidebar.warning("API Offline (Run uvicorn central_system.backend.api:app)")

tabs = st.tabs(["🐋 Whale Tracker", "🚨 Suspicious Activity", "🗺️ Wallet Clustering", "🤖 AI Forensic Reports"])

with tabs[0]:
    st.header("Real-time Whale Activity")
    try:
        whales = requests.get(f"{API_URL}/whales").json()
        if whales:
            df = pd.DataFrame(whales)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No whales detected yet.")
    except:
        st.error("Failed to fetch whale data")

with tabs[1]:
    st.header("Statistical Insider Detection (P-Value Analysis)")
    try:
        suspicious = requests.get(f"{API_URL}/suspicious-wallets").json()
        if suspicious:
            df_sus = pd.DataFrame(suspicious)
            st.dataframe(df_sus, use_container_width=True)

            # Manual trigger
            selected_wallet = st.selectbox("Select wallet for deep AI analysis", df_sus['address'].tolist() if not df_sus.empty else [])
            if st.button("Run Gemini 2.0 Forensics"):
                res = requests.post(f"{API_URL}/trigger-manual-analysis/{selected_wallet}")
                st.success(f"Analysis triggered: {res.json().get('status')}")
        else:
            st.info("Scanning for anomalies...")
    except:
        st.error("Failed to fetch suspicious data")

with tabs[2]:
    st.header("Wallet Clustering Map")
    try:
        clusters = requests.get(f"{API_URL}/clusters").json()
        if clusters:
            df_clu = pd.DataFrame(clusters)
            st.dataframe(df_clu, use_container_width=True)
            st.info(f"Identified {len(clusters)} suspicious wallet clusters.")
        else:
            st.info("No suspicious clusters identified yet.")
    except:
        st.error("Failed to fetch clustering data")

with tabs[3]:
    st.header("AI Forensic Intelligence")
    st.markdown("""
    Automated reports from **Gemini 2.0 Flash** with search grounding.
    """)

    try:
        alerts = requests.get(f"{API_URL}/alerts").json()
        if alerts:
            for alert in alerts:
                with st.expander(f"🚩 {alert['wallet_address'][:10]}... | {alert['market_question'][:50]}..."):
                    st.write(f"**Value:** ${alert['value_usd']:,.2f}")
                    st.write(f"**Price Shift:** {alert.get('price_shift', 'N/A')}")
                    analysis = alert.get('ai_analysis', {})
                    st.write(f"**AI Score:** {analysis.get('insider_probability_score', 'N/A')}/100")
                    st.write(f"**Reasoning:** {analysis.get('reasoning', 'No analysis available.')}")
        else:
            st.info("No AI forensic reports generated yet.")
    except:
        st.error("Failed to fetch alerts from API")

# Auto-refresh
time.sleep(10)
st.rerun()
