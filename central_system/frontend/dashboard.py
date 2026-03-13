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
    stats = requests.get(f"{API_URL}/stats").json()
    st.sidebar.metric("Trades Analyzed", stats.get("total_trades_analyzed", 0))
    st.sidebar.metric("Wallets Tracked", stats.get("unique_wallets_tracked", 0))
except:
    st.sidebar.warning("API Offline")

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
    st.info("Clustering algorithm is identifying linked wallets via timing and market overlap...")
    st.image("https://via.placeholder.com/800x400.png?text=Wallet+Network+Graph+Placeholder", caption="Network visualization logic integrated in backend")

with tabs[3]:
    st.header("AI Forensic Intelligence")
    st.markdown("""
    This section displays automated reports from **Gemini 2.0 Flash** after cross-referencing trades with public news leaks.
    Check Discord or Slack for real-time alert embeds.
    """)
    st.code("""
    [REPORT] Wallet 0x123... flagged with 92% Insider Probability.
    Reasoning: Trade occurred 12 minutes before Bloomberg report. No prior public mention found via Google Search grounding.
    """)

# Auto-refresh
time.sleep(10)
st.rerun()
