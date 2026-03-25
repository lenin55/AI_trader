"""
Streamlit Dashboard for rupee50k-ai-sector-trader.
Provides visibility into logs, config, and daily execution status.
Run with: streamlit run dashboard.py
"""

import streamlit as st
import os
import json
from config import LIVE_MODE, MAX_RISK_PER_TRADE, TOTAL_CAPITAL

st.set_page_config(page_title="Rupee50k AI Sector Trader", layout="wide")

st.title("🤖 Rupee50k AI Sector Trader Dashboard")

st.sidebar.header("System Status")
mode_color = "🔴 LIVE MODE" if LIVE_MODE else "🟢 PAPER MODE (Safe)"
st.sidebar.markdown(f"**Mode:** {mode_color}")

st.sidebar.markdown("### Risk Parameters")
st.sidebar.markdown(f"- **Capital:** ₹{TOTAL_CAPITAL}")
st.sidebar.markdown(f"- **Max Risk / Trade:** ₹{MAX_RISK_PER_TRADE}")
st.sidebar.markdown("- **Order Type:** CNC Delivery")

st.header("Execution Logs")
log_file = "logs/trading_bot.log"

if os.path.exists(log_file):
    with open(log_file, "r") as f:
        # Read last 50 lines
        lines = f.readlines()
        recent_logs = "".join(lines[-50:])
    
    st.code(recent_logs, language="log")
else:
    st.info("No logs found yet. The bot hasn't run.")

st.header("Manual Execution & Overrides")
st.warning("Clicking below will trigger the full AI analysis loop immediately.")

if st.button("▶️ Run Daily Routine Now"):
    with st.spinner("Running AI Analysis & Trading Logic..."):
        from trading_logic import SectorTrader
        trader = SectorTrader()
        result = trader.execute_daily_routine()
        
        if result.get("status") == "success":
            st.success(f"Routine Finished. Action Taken: {result.get('action')}")
            st.json(result)
        else:
            st.error(f"Routine Failed: {result.get('message', 'Unknown Error')}")

st.markdown("---")
st.caption("Designed for highly conservative NSE trading. Disclaimer: For educational purposes.")
