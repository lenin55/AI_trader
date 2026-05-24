"""
Streamlit Dashboard for NiftyMind.
Dark trading terminal aesthetic — neon accents, glassmorphism cards, live ticker strip.

Run with: streamlit run dashboard.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np

import sys
import importlib
import dotenv

# Force-reload config on every Streamlit run to capture dynamic .env changes instantly
dotenv.load_dotenv(override=True)
if 'config' in sys.modules:
    importlib.reload(sys.modules['config'])

from config import LIVE_MODE, MAX_RISK_PER_TRADE, TOTAL_CAPITAL

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NiftyMind",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Full dark terminal CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --bg:           #080C14;
        --bg2:          #0D1321;
        --bg3:          #111827;
        --border:       rgba(255,255,255,0.06);
        --border-glow:  rgba(0,212,255,0.3);
        --text:         #E2E8F0;
        --text-dim:     #64748B;
        --text-muted:   #334155;
        --green:        #00FF88;
        --green-dim:    rgba(0,255,136,0.15);
        --green-glow:   0 0 20px rgba(0,255,136,0.3);
        --red:          #FF4757;
        --red-dim:      rgba(255,71,87,0.15);
        --red-glow:     0 0 20px rgba(255,71,87,0.3);
        --blue:         #00D4FF;
        --blue-dim:     rgba(0,212,255,0.12);
        --blue-glow:    0 0 20px rgba(0,212,255,0.3);
        --gold:         #FFD700;
        --purple:       #A855F7;
        --font:         'Inter', sans-serif;
        --mono:         'JetBrains Mono', monospace;
    }

    /* === BASE === */
    html, body, [class*="css"] {
        font-family: var(--font);
        background-color: var(--bg) !important;
        color: var(--text);
    }
    .main, .main > div, .block-container {
        background-color: var(--bg) !important;
        padding-top: 0 !important;
    }
    .block-container { padding: 0 2rem 2rem 2rem !important; max-width: 100% !important; }
    h1, h2, h3, h4 { font-family: var(--font); letter-spacing: -0.02em; font-weight: 700; color: var(--text); }

    /* === HIDE streamlit branding, but keep the header-mounted sidebar toggle alive === */
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stHeader"] {
        background: transparent !important;
        border: 0 !important;
        height: 0 !important;
        z-index: 2000 !important;
    }
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"] {
        display: none !important;
    }

    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background: var(--bg2) !important;
        border-right: 1px solid var(--border) !important;
        position: relative !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        background: var(--bg2) !important;
        padding: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    /* Kill every layer of Streamlit's default top padding in the sidebar */
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"],
    [data-testid="stSidebarHeader"],
    [data-testid="stSidebar"] > div > div,
    [data-testid="stSidebar"] section,
    [data-testid="stSidebar"] .css-1d391kg,
    [data-testid="stSidebar"] .css-18ni7ap,
    [data-testid="stSidebar"] .css-pkbazv {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        margin-top: 0 !important;
    }
    /* Collapse the collapse-button wrapper so it takes zero height in DOM flow */
    [data-testid="stSidebarCollapseButton"] {
        height: 0 !important;
        overflow: visible !important;
    }

    /* === METRIC CONTAINERS === */
    [data-testid="metric-container"] {
        background: var(--bg3) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: 14px 16px !important;
    }
    [data-testid="metric-container"] > div { color: var(--text-dim) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.08em; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: var(--text) !important; font-family: var(--mono) !important; font-weight: 700 !important; font-size: 1.4rem !important; }
    [data-testid="stMetricDelta"] { font-family: var(--mono) !important; font-size: 0.8rem !important; }

    /* === BUTTONS === */
    .stButton > button {
        background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,212,255,0.05)) !important;
        color: var(--blue) !important;
        border: 1px solid rgba(0,212,255,0.4) !important;
        border-radius: 8px !important;
        font-family: var(--font) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        padding: 8px 18px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        letter-spacing: 0.05em !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(0,212,255,0.1)) !important;
        box-shadow: 0 0 16px rgba(0,212,255,0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg2) !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 4px !important;
        padding: 0 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--text-dim) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        letter-spacing: 0.05em !important;
        background: transparent !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 12px 20px !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--blue) !important;
        background: rgba(0,212,255,0.06) !important;
        border-bottom: 2px solid var(--blue) !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text) !important;
        background: rgba(255,255,255,0.03) !important;
    }

    /* === DATAFRAMES === */
    .stDataFrame { border: 1px solid var(--border) !important; border-radius: 10px !important; overflow: hidden !important; }
    [data-testid="stDataFrame"] table { background: var(--bg3) !important; }
    [data-testid="stDataFrame"] th { background: var(--bg2) !important; color: var(--text-dim) !important; font-size: 11px !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; font-weight: 600 !important; border-bottom: 1px solid var(--border) !important; }
    [data-testid="stDataFrame"] td { color: var(--text) !important; font-family: var(--mono) !important; font-size: 13px !important; border-bottom: 1px solid rgba(255,255,255,0.03) !important; }
    [data-testid="stDataFrame"] tr:hover td { background: rgba(255,255,255,0.03) !important; }

    /* === INPUTS === */
    .stDateInput > div > div, .stSelectbox > div > div {
        background: var(--bg3) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        border-radius: 8px !important;
    }

    /* === EXPANDERS === */
    [data-testid="stExpander"] {
        background: var(--bg3) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }

    /* === INFO/WARNING BOXES === */
    .stInfo, .stAlert { background: var(--bg3) !important; border-radius: 8px !important; }

    /* === DIVIDER === */
    hr { border-color: var(--border) !important; margin: 16px 0 !important; }

    /* =========================================
       CUSTOM COMPONENTS
    ========================================= */

    /* TICKER STRIP — rendered with inline styles, no CSS classes needed */

    /* HEADER BAR */
    .header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 24px;
        background: var(--bg2);
        border-bottom: 1px solid var(--border);
        margin-bottom: 0;
    }
    .header-logo {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .header-logo-icon {
        width: 36px; height: 36px;
        background: linear-gradient(135deg, #00D4FF, #0066FF);
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px;
    }
    .header-title {
        font-size: 16px;
        font-weight: 800;
        color: var(--text);
        letter-spacing: -0.01em;
    }
    .header-subtitle {
        font-size: 11px;
        color: var(--text-dim);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .header-badge {
        font-family: var(--mono);
        font-size: 11px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: 0.1em;
        animation: pulse-badge 2s infinite;
    }
    .badge-live   { background: rgba(255,71,87,0.15); color: var(--red); border: 1px solid rgba(255,71,87,0.4); }
    .badge-paper  { background: rgba(0,255,136,0.1);  color: var(--green); border: 1px solid rgba(0,255,136,0.3); }
    @keyframes pulse-badge {
        0%,100% { opacity:1; }
        50%      { opacity:0.6; }
    }

    /* NEON METRIC CARD */
    .neon-card {
        background: var(--bg3);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px 20px 16px;
        position: relative;
        overflow: hidden;
        transition: all 0.25s ease;
    }
    .neon-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        border-radius: 12px 12px 0 0;
        opacity: 0.8;
    }
    .neon-card-green::before  { background: var(--green); box-shadow: 0 0 12px var(--green); }
    .neon-card-red::before    { background: var(--red);   box-shadow: 0 0 12px var(--red); }
    .neon-card-blue::before   { background: var(--blue);  box-shadow: 0 0 12px var(--blue); }
    .neon-card-gold::before   { background: var(--gold);  box-shadow: 0 0 12px var(--gold); }
    .neon-card-purple::before { background: var(--purple);box-shadow: 0 0 12px var(--purple); }
    .neon-card:hover { border-color: rgba(255,255,255,0.12); transform: translateY(-2px); }
    .neon-label {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--text-dim);
        margin-bottom: 10px;
    }
    .neon-value {
        font-family: var(--mono);
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 6px;
    }
    .neon-sub {
        font-size: 12px;
        color: var(--text-dim);
    }
    .neon-green  { color: var(--green); }
    .neon-red    { color: var(--red); }
    .neon-blue   { color: var(--blue); }
    .neon-gold   { color: var(--gold); }
    .neon-purple { color: var(--purple); }
    .neon-white  { color: var(--text); }

    /* DECISION BANNER */
    .decision-banner {
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        border-left: 4px solid;
        backdrop-filter: blur(8px);
    }
    .decision-buy    { background: rgba(0,255,136,0.06); border-color: var(--green); }
    .decision-notrade{ background: rgba(255,215,0,0.06);  border-color: var(--gold); }
    .decision-other  { background: rgba(0,212,255,0.06);  border-color: var(--blue); }
    .decision-title {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .decision-body  { font-size: 14px; color: var(--text); line-height: 1.6; }

    /* SIDEBAR NAV */
    .nav-section {
        padding: 6px 12px 4px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: var(--text-muted);
        text-transform: uppercase;
        margin-top: 8px;
    }
    .sidebar-logo-block {
        padding: 12px 16px 12px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 0;
    }
    .sidebar-logo-title {
        font-size: 15px;
        font-weight: 800;
        color: var(--text);
        letter-spacing: -0.01em;
    }
    .sidebar-logo-sub {
        font-size: 10px;
        color: var(--text-dim);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 2px;
    }
    .stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        border-radius: 8px;
        margin: 2px 8px;
        transition: background 0.15s ease;
    }
    .stat-row:hover { background: rgba(255,255,255,0.03); }
    .stat-key { font-size: 12px; color: var(--text-dim); }
    .stat-val { font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--text); }
    .stat-val-green  { color: var(--green); }
    .stat-val-red    { color: var(--red); }

    /* SECTION HEADER */
    .section-title {
        font-size: 14px;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.01em;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-title-dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--blue);
        box-shadow: 0 0 6px var(--blue);
        display: inline-block;
    }

    /* PNL PILL */
    .pnl-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 20px;
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 600;
    }
    .pnl-up   { background: rgba(0,255,136,0.1);  color: var(--green); border: 1px solid rgba(0,255,136,0.25); }
    .pnl-down { background: rgba(255,71,87,0.1);   color: var(--red);   border: 1px solid rgba(255,71,87,0.25); }

    /* EVAL CARD */
    .eval-card {
        background: var(--bg3);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .eval-hold { border-left: 3px solid var(--green); }
    .eval-sell { border-left: 3px solid var(--red); }

    /* === SIDEBAR TOGGLE — absolutely positioned inside sidebar top-right === */
    [data-testid="stSidebarCollapseButton"] {
        position: absolute !important;
        top: 10px !important;
        right: 10px !important;
        z-index: 999 !important;
        display: block !important;
        visibility: visible !important;
    }
    [data-testid="stSidebarCollapseButton"] button {
        background: rgba(0,212,255,0.1) !important;
        border: 1px solid rgba(0,212,255,0.3) !important;
        border-radius: 8px !important;
        color: #00D4FF !important;
        width: 36px !important;
        height: 36px !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        background: rgba(0,212,255,0.25) !important;
        box-shadow: 0 0 12px rgba(0,212,255,0.4) !important;
    }
    [data-testid="stSidebarCollapseButton"] svg {
        stroke: #00D4FF !important;
        width: 20px !important;
        height: 20px !important;
    }

    /* === PORTFOLIO SCROLL AREA === */
    .portfolio-scroll-area {
        overflow-y: auto;
        max-height: calc(100vh - 310px);
        scrollbar-width: thin;
        scrollbar-color: rgba(0,212,255,0.3) transparent;
    }
    .portfolio-scroll-area::-webkit-scrollbar { width: 4px; }
    .portfolio-scroll-area::-webkit-scrollbar-track { background: transparent; }
    .portfolio-scroll-area::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.3); border-radius: 2px; }
    /* The expand button (in main area when sidebar is collapsed) */
    [data-testid="collapsedControl"] {
        position: fixed !important;
        top: 16px !important;
        left: 16px !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 3000 !important;
    }
    [data-testid="collapsedControl"] button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        background: rgba(0,212,255,0.12) !important;
        border: 1px solid rgba(0,212,255,0.35) !important;
        border-radius: 8px !important;
        color: #00D4FF !important;
        width: 40px !important;
        height: 40px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3) !important;
    }
    [data-testid="collapsedControl"] button:hover {
        background: rgba(0,212,255,0.28) !important;
        box-shadow: 0 0 16px rgba(0,212,255,0.4) !important;
    }
    [data-testid="collapsedControl"] svg {
        stroke: #00D4FF !important;
        width: 22px !important;
        height: 22px !important;
    }

    /* === SETTINGS PAGE === */
    .settings-section {
        background: var(--bg3);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .settings-section-title {
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--blue);
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .settings-hint {
        font-size: 11px;
        color: var(--text-muted);
        margin-top: 4px;
        line-height: 1.5;
    }
    .save-success {
        background: rgba(0,255,136,0.08);
        border: 1px solid rgba(0,255,136,0.3);
        border-radius: 8px;
        padding: 12px 16px;
        color: var(--green);
        font-size: 13px;
        font-weight: 600;
    }

    /* Override Streamlit form inputs inside settings */
    .stTextInput input, .stNumberInput input {
        background: var(--bg2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
        font-family: var(--mono) !important;
        font-size: 13px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: rgba(0,212,255,0.4) !important;
        box-shadow: 0 0 0 2px rgba(0,212,255,0.1) !important;
    }
    .stCheckbox label { color: var(--text) !important; font-size: 14px !important; }
    .stCheckbox > label > div[data-testid="stCheckbox"] { border-color: var(--border) !important; }
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,255,136,0.08)) !important;
        color: var(--green) !important;
        border: 1px solid rgba(0,255,136,0.4) !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        padding: 10px 28px !important;
        border-radius: 8px !important;
        font-size: 13px !important;
    }
    [data-testid="stFormSubmitButton"] > button:hover {
        box-shadow: 0 0 16px rgba(0,255,136,0.3) !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Safe DB import ─────────────────────────────────────────────────────────────
def try_import_db():
    try:
        from database import (
            get_open_trades, get_trade_history,
            get_portfolio_summary, get_news_for_date,
            get_today_decision, initialize_database,
            get_equity_history
        )
        initialize_database()
        return get_open_trades, get_trade_history, get_portfolio_summary, get_news_for_date, get_today_decision, get_equity_history, None
    except Exception as e:
        return None, None, None, None, None, None, str(e)

(get_open_trades, get_trade_history,
 get_portfolio_summary, get_news_for_date, get_today_decision, get_equity_history, db_error) = try_import_db()


# ── Live ticker helper ─────────────────────────────────────────────────────────
def get_ticker_prices():
    """Fetch LTP for a short list of key NSE stocks. No caching — KiteClient is not serialisable."""
    from config import LIQUID_UNIVERSE
    try:
        from kite_client import KiteClient
        kite   = KiteClient()
        sample = LIQUID_UNIVERSE[:10]
        prices = {}
        for sym in sample:
            try:
                ltp = kite.get_ltp(sym)
                prices[sym] = ltp if ltp and ltp > 0 else None
            except Exception:
                prices[sym] = None
        return prices
    except Exception:
        return {}


def render_ticker_strip():
    """Render a horizontal ticker bar with key NSE stock prices."""
    try:
        prices = get_ticker_prices()
        if not prices:
            return

        # Build each chip as a single compact inline string (no newlines inside)
        chips = []
        for sym, price in prices.items():
            price_str = f"&#8377;{price:,.2f}" if price else "&mdash;"
            chip = (
                f'<span style="display:inline-flex;align-items:center;gap:6px;margin:0 12px;'
                f'font-family:\'JetBrains Mono\',monospace;font-size:12px;white-space:nowrap;">'
                f'<b style="color:#E2E8F0;letter-spacing:0.04em;">{sym}</b>'
                f'<span style="color:#00FF88;">&#9650; {price_str}</span>'
                f'</span>'
            )
            chips.append(chip)

        sep = '<span style="color:rgba(255,255,255,0.15);font-size:10px;">&#124;</span>'
        row = sep.join(chips)

        html = (
            '<div style="background:#0D1321;border-bottom:1px solid rgba(255,255,255,0.06);'
            'padding:9px 20px;overflow-x:auto;white-space:nowrap;scrollbar-width:none;">'
            + row +
            '</div>'
        )
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        pass  # Ticker is decorative — never crash the dashboard over it


def render_sidebar_toggle():
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const btnId = "apex-sidebar-toggle";

        function clickNativeSidebarToggle() {
            const selectors = [
                '[data-testid="collapsedControl"] button',
                '[data-testid="stSidebarCollapseButton"] button'
            ];

            for (const selector of selectors) {
                const button = doc.querySelector(selector);
                if (button) {
                    button.click();
                    return;
                }
            }
        }

        function applyBaseStyle(button) {
            Object.assign(button.style, {
                position: "fixed",
                top: "16px",
                left: "16px",
                width: "42px",
                height: "42px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "0",
                borderRadius: "10px",
                border: "1px solid rgba(0,212,255,0.38)",
                background: "rgba(0,212,255,0.14)",
                color: "#00D4FF",
                fontSize: "22px",
                lineHeight: "1",
                cursor: "pointer",
                zIndex: "5000",
                boxShadow: "0 6px 18px rgba(0,0,0,0.35)"
            });
        }

        function ensureToggleButton() {
            let button = doc.getElementById(btnId);

            if (!button) {
                button = doc.createElement("button");
                button.id = btnId;
                button.type = "button";
                button.title = "Toggle sidebar";
                button.setAttribute("aria-label", "Toggle sidebar");
                button.innerHTML = "☰";
                applyBaseStyle(button);
                button.onclick = clickNativeSidebarToggle;
                button.onmouseenter = () => {
                    button.style.background = "rgba(0,212,255,0.24)";
                    button.style.boxShadow = "0 0 16px rgba(0,212,255,0.4)";
                };
                button.onmouseleave = () => {
                    button.style.background = "rgba(0,212,255,0.14)";
                    button.style.boxShadow = "0 6px 18px rgba(0,0,0,0.35)";
                };
                doc.body.appendChild(button);
            } else {
                applyBaseStyle(button);
            }
        }

        ensureToggleButton();
        window.setInterval(ensureToggleButton, 1000);
        </script>
        """,
        height=0,
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    mode_label = "LIVE" if LIVE_MODE else "PAPER"
    mode_class = "badge-live" if LIVE_MODE else "badge-paper"

    st.markdown(f"""
    <div class="sidebar-logo-block">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
            <div style="width:32px;height:32px;background:linear-gradient(135deg,#00D4FF,#0066FF);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;">⚡</div>
            <div>
                <div class="sidebar-logo-title">NiftyMind</div>
                <div class="sidebar-logo-sub">NSE Algo Intelligence</div>
            </div>
        </div>
        <span class="header-badge {mode_class}">{mode_label} MODE</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Interactive Mode Toggle & Actions at the Top ──
    st.markdown('<div class="nav-section" style="margin-top: 4px;">Trading Control</div>', unsafe_allow_html=True)
    st.markdown("<div style='padding: 0 8px; display: flex; flex-direction: column; gap: 8px;'>", unsafe_allow_html=True)
    
    import dotenv
    is_live = st.toggle("🟢 Go LIVE Mode", value=LIVE_MODE, help="Switch between Paper Mode (Simulated) and Live Mode (Zerodha)")
    if is_live != LIVE_MODE:
        dotenv.set_key(".env", "LIVE_MODE", "True" if is_live else "False")
        st.success(f"Switched to {'LIVE' if is_live else 'PAPER'} mode!")
        st.rerun()

    if st.button("⚡ Execute Daily Analysis", use_container_width=True, type="primary"):
        with st.spinner("Running AI analysis..."):
            try:
                from trading_logic import NiftyMind
                trader = NiftyMind()
                result = trader.execute_daily_routine()
                if result.get("status") == "success":
                    st.success(f"✅ {result.get('action')}")
                else:
                    st.error(result.get("message", "Unknown error"))
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("↺ Refresh Data", use_container_width=True):
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.06);margin:12px 8px;"></div>', unsafe_allow_html=True)

    # Portfolio metrics — computed before building the single HTML block
    summary = get_portfolio_summary() if not db_error else {}
    pnl_total = float(summary.get("total_realised_pnl", 0))
    pnl_pct   = (pnl_total / TOTAL_CAPITAL) * 100
    open_pos  = int(summary.get("open_positions", 0))
    closed_trades = int(summary.get("closed_trades", 0))
    wins      = int(summary.get("winning_trades", 0))
    win_rate  = (wins / max(closed_trades, 1)) * 100

    pnl_class = "stat-val-green" if pnl_total >= 0 else "stat-val-red"
    pnl_sign  = "+" if pnl_total >= 0 else ""

    # ── Single markdown block so the scroll wrapper actually wraps the content ──
    st.markdown(f"""
    <div class="portfolio-scroll-area">
        <div class="nav-section">Portfolio</div>
        <div class="stat-row"><span class="stat-key">Capital</span><span class="stat-val">₹{TOTAL_CAPITAL:,.0f}</span></div>
        <div class="stat-row"><span class="stat-key">Realised P&amp;L</span><span class="stat-val {pnl_class}">{pnl_sign}₹{pnl_total:,.2f}</span></div>
        <div class="stat-row"><span class="stat-key">Return</span><span class="stat-val {pnl_class}">{pnl_sign}{pnl_pct:.2f}%</span></div>
        <div class="stat-row"><span class="stat-key">Open Positions</span><span class="stat-val">{open_pos}</span></div>
        <div class="stat-row"><span class="stat-key">Closed Trades</span><span class="stat-val">{closed_trades}</span></div>
        <div class="stat-row"><span class="stat-key">Win Rate</span><span class="stat-val neon-green">{win_rate:.1f}%</span></div>
        <div style="height:1px;background:rgba(255,255,255,0.06);margin:12px 8px;"></div>
        <div class="nav-section">Risk Parameters</div>
        <div class="stat-row"><span class="stat-key">Max Risk/Trade</span><span class="stat-val">₹{MAX_RISK_PER_TRADE:,.0f}</span></div>
        <div class="stat-row"><span class="stat-key">Stop-Loss</span><span class="stat-val neon-red">-5.0%</span></div>
        <div class="stat-row"><span class="stat-key">Profit Target</span><span class="stat-val neon-green">+15.0%</span></div>
        <div class="stat-row"><span class="stat-key">Trailing Stop</span><span class="stat-val" style="color:var(--gold)">-3.0%</span></div>
    </div>
    """, unsafe_allow_html=True)


# ── Main area ──────────────────────────────────────────────────────────────────
if db_error:
    st.error(f"⚠️ Database connection failed: `{db_error}`")
    st.info("Set `DATABASE_URL` in your `.env` file and ensure PostgreSQL is running.")
    st.stop()

# Live ticker strip
render_ticker_strip()
render_sidebar_toggle()

# ── Header bar ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="header-bar">
    <div class="header-logo">
        <div class="header-logo-icon">⚡</div>
        <div>
            <div class="header-title">NiftyMind</div>
            <div class="header-subtitle">NSE Delivery · Gemini AI Engine · Algo Intelligence</div>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
        <span style="font-size:12px; color:var(--text-dim); font-family:var(--mono);">{date.today().strftime('%d %b %Y')}</span>
        <span class="header-badge {'badge-live' if LIVE_MODE else 'badge-paper'}">{'● LIVE' if LIVE_MODE else '◎ PAPER'}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

# ── Today's AI Decision Banner ─────────────────────────────────────────────────
today_decision = get_today_decision(date.today()) if get_today_decision else None

if today_decision:
    action = today_decision.get("action", "UNKNOWN")
    reason = today_decision.get("reason", "No reason provided.")

    if action == "BUY":
        cls, icon, color, label = "decision-buy", "🚀", "var(--green)", "BUY SIGNAL ACTIVE"
    elif action == "NO_TRADE":
        cls, icon, color, label = "decision-notrade", "🛡️", "var(--gold)", "CAPITAL PRESERVATION"
    elif action == "HALTED":
        cls, icon, color, label = "decision-notrade", "⛔", "var(--red)", "CIRCUIT BREAKER TRIGGERED"
    else:
        cls, icon, color, label = "decision-other", "🔄", "var(--blue)", action

    st.markdown(f"""
    <div class="decision-banner {cls}">
        <div class="decision-title" style="color:{color};">{icon} &nbsp; TODAY'S VERDICT — {label}</div>
        <div class="decision-body">{reason}</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="decision-banner decision-other">
        <div class="decision-title" style="color:var(--blue);">💡 &nbsp; ANALYSIS PENDING</div>
        <div class="decision-body" style="color:var(--text-dim);">AI has not evaluated the market today. Run the analysis from the sidebar.</div>
    </div>
    """, unsafe_allow_html=True)

# ── KPI row ───────────────────────────────────────────────────────────────────
summary       = get_portfolio_summary()
open_trades_data = get_open_trades()

pnl           = float(summary.get("total_realised_pnl", 0))
pnl_pct_kpi   = (pnl / TOTAL_CAPITAL) * 100
wins_kpi      = int(summary.get("winning_trades", 0))
closed_kpi    = int(summary.get("closed_trades", 0) or 1)
win_rate_kpi  = (wins_kpi / closed_kpi) * 100
open_pos_kpi  = int(summary.get("open_positions", 0))

pnl_sign = "+" if pnl >= 0 else ""
pnl_color_cls  = "neon-green" if pnl >= 0 else "neon-red"
neon_card_pnl  = "neon-card-green" if pnl >= 0 else "neon-card-red"

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(f"""
    <div class="neon-card neon-card-blue">
        <div class="neon-label">Open Positions</div>
        <div class="neon-value neon-blue">{open_pos_kpi}</div>
        <div class="neon-sub">Active holdings</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="neon-card neon-card-purple">
        <div class="neon-label">Closed Trades</div>
        <div class="neon-value neon-purple">{closed_kpi}</div>
        <div class="neon-sub">Total executed</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="neon-card {neon_card_pnl}">
        <div class="neon-label">Realised P&amp;L</div>
        <div class="neon-value {pnl_color_cls}">{pnl_sign}₹{abs(pnl):,.0f}</div>
        <div class="neon-sub">{pnl_sign}{pnl_pct_kpi:.2f}% on capital</div>
    </div>""", unsafe_allow_html=True)

with c4:
    wr_cls = "neon-green" if win_rate_kpi >= 50 else "neon-red"
    st.markdown(f"""
    <div class="neon-card {'neon-card-green' if win_rate_kpi >= 50 else 'neon-card-red'}">
        <div class="neon-label">Win Rate</div>
        <div class="neon-value {wr_cls}">{win_rate_kpi:.1f}%</div>
        <div class="neon-sub">{wins_kpi}W / {closed_kpi - wins_kpi}L</div>
    </div>""", unsafe_allow_html=True)

with c5:
    roi_cls = "neon-green" if pnl_pct_kpi >= 0 else "neon-red"
    st.markdown(f"""
    <div class="neon-card neon-card-gold">
        <div class="neon-label">Return on Capital</div>
        <div class="neon-value neon-gold">{pnl_sign}{pnl_pct_kpi:.2f}%</div>
        <div class="neon-sub">₹{TOTAL_CAPITAL:,.0f} deployed</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "  💼  POSITIONS  ",
    "  📋  HISTORY  ",
    "  📊  ANALYTICS  ",
    "  📰  NEWS & LOGS  ",
    "  ⚙️  SETTINGS  ",
    "  🧪  BACKTEST LAB  ",
])


# ══════════════════════════════════════════════════════════
# TAB 1 — Open Positions
# ══════════════════════════════════════════════════════════
with tab1:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    if not open_trades_data:
        st.markdown("""
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:40px;text-align:center;">
            <div style="font-size:40px;margin-bottom:12px;">💰</div>
            <div style="font-size:16px;font-weight:700;color:var(--text);">No Open Positions</div>
            <div style="font-size:13px;color:var(--text-dim);margin-top:6px;">The portfolio is fully in cash. Run the daily analysis to evaluate opportunities.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        from kite_client import KiteClient
        kite = KiteClient()

        rows = []
        total_current_value = 0
        total_entry_value   = 0

        for t in open_trades_data:
            entry   = float(t["entry_price"])
            qty     = int(t["quantity"])
            ltp     = kite.get_ltp(t["stock"])
            pnl_pos = (ltp - entry) * qty
            pnl_pct_pos = ((ltp - entry) / entry) * 100
            sl_price    = entry * 0.95
            tp_price    = entry * 1.15
            cv  = ltp * qty
            ev  = entry * qty
            total_current_value += cv
            total_entry_value   += ev

            rows.append({
                "Stock":        t["stock"],
                "Sector":       t["sector"] or "—",
                "Qty":          qty,
                "Entry":        entry,
                "LTP":          ltp,
                "P&L ₹":        pnl_pos,
                "P&L %":        pnl_pct_pos,
                "Stop-Loss":    sl_price,
                "Target":       tp_price,
                "Entry Date":   str(t["entry_date"]),
                "Days Held":    (date.today() - t["entry_date"]).days,
            })

        # Summary metrics
        total_unrealized = sum(r["P&L ₹"] for r in rows)
        overall_pct = ((total_current_value - total_entry_value) / total_entry_value) * 100 if total_entry_value > 0 else 0
        tu_sign = "+" if total_unrealized >= 0 else ""
        tu_cls  = "neon-card-green" if total_unrealized >= 0 else "neon-card-red"
        tv_cls  = "neon-green" if total_unrealized >= 0 else "neon-red"

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.markdown(f"""<div class="neon-card neon-card-blue">
                <div class="neon-label">Positions</div>
                <div class="neon-value neon-blue">{len(rows)}</div>
            </div>""", unsafe_allow_html=True)
        with mc2:
            st.markdown(f"""<div class="neon-card {tu_cls}">
                <div class="neon-label">Unrealised P&amp;L</div>
                <div class="neon-value {tv_cls}">{tu_sign}₹{abs(total_unrealized):,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with mc3:
            st.markdown(f"""<div class="neon-card neon-card-purple">
                <div class="neon-label">Current Value</div>
                <div class="neon-value neon-purple">₹{total_current_value:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with mc4:
            op_cls = "neon-card-green" if overall_pct >= 0 else "neon-card-red"
            op_vcls = "neon-green" if overall_pct >= 0 else "neon-red"
            st.markdown(f"""<div class="neon-card {op_cls}">
                <div class="neon-label">Overall Return</div>
                <div class="neon-value {op_vcls}">{'+'if overall_pct>=0 else ''}{overall_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Position Details</div>', unsafe_allow_html=True)

        # Build styled df
        df_pos = pd.DataFrame(rows)
        df_display = df_pos[["Stock","Sector","Qty","Entry","LTP","P&L ₹","P&L %","Stop-Loss","Target","Days Held"]].copy()
        df_display["Entry"]     = df_display["Entry"].apply(lambda x: f"₹{x:,.2f}")
        df_display["LTP"]       = df_display["LTP"].apply(lambda x: f"₹{x:,.2f}")
        df_display["P&L ₹"]    = df_display["P&L ₹"].apply(lambda x: f"{'+'if x>=0 else ''}₹{x:,.2f}")
        df_display["P&L %"]    = df_display["P&L %"].apply(lambda x: f"{'+'if x>=0 else ''}{x:.2f}%")
        df_display["Stop-Loss"] = df_display["Stop-Loss"].apply(lambda x: f"₹{x:,.2f}")
        df_display["Target"]    = df_display["Target"].apply(lambda x: f"₹{x:,.2f}")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # P&L chart
        if rows:
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="section-title"><span class="section-title-dot"></span> Unrealised P&L per Position</div>', unsafe_allow_html=True)

            pnl_vals  = [r["P&L ₹"] for r in rows]
            syms      = [r["Stock"] for r in rows]
            bar_colors = ["#00FF88" if v >= 0 else "#FF4757" for v in pnl_vals]

            fig_pos = go.Figure()
            fig_pos.add_trace(go.Bar(
                x=syms, y=pnl_vals,
                marker=dict(
                    color=bar_colors,
                    line=dict(width=0),
                    opacity=0.85,
                ),
                text=[f"₹{v:+,.0f}" for v in pnl_vals],
                textposition="outside",
                textfont=dict(family="JetBrains Mono", size=11, color="#E2E8F0"),
                hovertemplate="<b>%{x}</b><br>P&L: ₹%{y:,.2f}<extra></extra>",
            ))
            fig_pos.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748B", family="Inter"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=12)),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="₹", tickfont=dict(color="#94A3B8", size=11)),
                height=340, margin=dict(t=20, b=20, l=20, r=20),
                showlegend=False,
            )
            st.plotly_chart(fig_pos, use_container_width=True)

    # Today's AI Evaluations
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="section-title-dot"></span> Today\'s AI Evaluations</div>', unsafe_allow_html=True)
    try:
        import psycopg2, psycopg2.extras, os
        from dotenv import load_dotenv
        load_dotenv()
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT te.*, t.stock FROM trade_evaluations te
                JOIN trades t ON t.id = te.trade_id
                WHERE te.eval_date = %s ORDER BY te.created_at DESC;
            """, (date.today(),))
            evals = cur.fetchall()
        conn.close()

        if evals:
            for ev in evals:
                is_hold   = ev["ai_verdict"] == "HOLD"
                card_cls  = "eval-hold" if is_hold else "eval-sell"
                v_color   = "var(--green)" if is_hold else "var(--red)"
                v_icon    = "🟢" if is_hold else "🔴"
                pnl_ev    = float(ev["current_pnl"])
                pnl_ev_sign = "+" if pnl_ev >= 0 else ""
                pnl_ev_cls  = "neon-green" if pnl_ev >= 0 else "neon-red"

                st.markdown(f"""
                <div class="eval-card {card_cls}">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <div style="font-weight:700;font-size:14px;color:var(--text);">{v_icon} {ev['stock']}</div>
                        <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:{v_color};">{ev['ai_verdict']}</span>
                    </div>
                    <div style="display:flex;gap:20px;margin-bottom:10px;">
                        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;">Price</div><div style="font-family:var(--mono);font-size:13px;">₹{float(ev['current_price']):,.2f}</div></div>
                        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;">P&L</div><div style="font-family:var(--mono);font-size:13px;color:{v_color};">{pnl_ev_sign}₹{abs(pnl_ev):,.2f} ({ev['pnl_pct']:+.2f}%)</div></div>
                        <div><div style="font-size:10px;color:var(--text-dim);text-transform:uppercase;">Thesis</div><div style="font-size:12px;color:{'var(--green)' if ev['thesis_intact'] else 'var(--red)'};">{'Intact' if ev['thesis_intact'] else 'Broken'}</div></div>
                    </div>
                    <div style="font-size:13px;color:var(--text-dim);line-height:1.5;">{ev['ai_reasoning']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:var(--text-dim);font-size:13px;">No evaluations recorded for today.</p>', unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<p style="color:var(--text-dim);font-size:13px;">Could not load evaluations: {e}</p>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# TAB 2 — Trade History
# ══════════════════════════════════════════════════════════
with tab2:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    history = get_trade_history(limit=100)
    if not history:
        st.markdown("""
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:40px;text-align:center;">
            <div style="font-size:40px;margin-bottom:12px;">📋</div>
            <div style="font-size:16px;font-weight:700;color:var(--text);">No Closed Trades Yet</div>
            <div style="font-size:13px;color:var(--text-dim);margin-top:6px;">Trade history will appear here once positions are closed.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        rows_hist = []
        for t in history:
            p = float(t["pnl"]) if t["pnl"] else 0
            rows_hist.append({
                "ID":          t["id"],
                "Stock":       t["stock"],
                "Sector":      t["sector"] or "—",
                "Qty":         t["quantity"],
                "Entry ₹":     f"₹{float(t['entry_price']):,.2f}",
                "Exit ₹":      f"₹{float(t['exit_price']):,.2f}" if t["exit_price"] else "—",
                "P&L":         f"{'+'if p>=0 else ''}₹{p:,.2f}",
                "Exit Reason": t["exit_reason"] or "—",
                "Entry Date":  str(t["entry_date"]),
                "Exit Date":   str(t["exit_date"]) if t["exit_date"] else "OPEN",
                "Status":      t["status"],
                "_pnl_num":    p,
            })

        df_hist = pd.DataFrame(rows_hist)

        def style_history(val):
            try:
                num = float(str(val).replace("₹","").replace(",","").replace("+",""))
                if num > 0:  return "color:#00FF88;font-weight:700;font-family:'JetBrains Mono',monospace"
                if num < 0:  return "color:#FF4757;font-weight:700;font-family:'JetBrains Mono',monospace"
            except Exception:
                pass
            return "font-family:'JetBrains Mono',monospace"

        display_cols = ["ID","Stock","Sector","Qty","Entry ₹","Exit ₹","P&L","Exit Reason","Entry Date","Exit Date","Status"]
        styled_hist = df_hist[display_cols].style.applymap(style_history, subset=["P&L"])
        st.dataframe(styled_hist, use_container_width=True, hide_index=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        # Charts
        col_h1, col_h2 = st.columns(2)

        with col_h1:
            st.markdown('<div class="section-title"><span class="section-title-dot"></span> Exit Reason Breakdown</div>', unsafe_allow_html=True)
            rc = df_hist["Exit Reason"].value_counts().reset_index()
            rc.columns = ["Reason","Count"]
            fig_pie = go.Figure(go.Pie(
                labels=rc["Reason"], values=rc["Count"],
                hole=0.55,
                marker=dict(colors=["#00FF88","#FF4757","#FFD700","#00D4FF","#A855F7"],
                            line=dict(color="#080C14", width=2)),
                textfont=dict(family="Inter", size=12),
                hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>",
            ))
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748B", family="Inter"),
                showlegend=True,
                legend=dict(font=dict(color="#94A3B8", size=11)),
                height=340, margin=dict(t=20,b=20,l=20,r=20),
                annotations=[dict(text="EXIT<br>REASONS", x=0.5, y=0.5, font_size=12,
                                  font_color="#64748B", showarrow=False)]
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_h2:
            st.markdown('<div class="section-title"><span class="section-title-dot"></span> Win vs Loss Distribution</div>', unsafe_allow_html=True)
            wl = df_hist[df_hist["_pnl_num"] != 0].copy()
            wl["Result"] = wl["_pnl_num"].apply(lambda x: "Win" if x > 0 else "Loss")
            wl_counts = wl["Result"].value_counts().reset_index()
            wl_counts.columns = ["Result","Count"]

            fig_wl = go.Figure(go.Bar(
                x=wl_counts["Result"], y=wl_counts["Count"],
                marker=dict(
                    color=["#00FF88" if r == "Win" else "#FF4757" for r in wl_counts["Result"]],
                    opacity=0.85, line=dict(width=0),
                ),
                text=wl_counts["Count"], textposition="outside",
                textfont=dict(family="JetBrains Mono", size=13, color="#E2E8F0"),
                hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
                width=0.4,
            ))
            fig_wl.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748B", family="Inter"),
                xaxis=dict(gridcolor="rgba(255,255,255,0)", tickfont=dict(color="#94A3B8", size=13, family="Inter")),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
                height=340, margin=dict(t=20,b=20,l=20,r=20),
                showlegend=False,
            )
            st.plotly_chart(fig_wl, use_container_width=True)


# ══════════════════════════════════════════════════════════
# TAB 3 — Analytics
# ══════════════════════════════════════════════════════════
with tab3:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    history_a = get_trade_history(limit=200)
    closed_a  = [t for t in history_a if t["status"] == "CLOSED" and t["pnl"] is not None]

    if not closed_a:
        st.markdown("""
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:40px;text-align:center;">
            <div style="font-size:40px;margin-bottom:12px;">📊</div>
            <div style="font-size:16px;font-weight:700;color:var(--text);">Analytics Available After First Trade</div>
            <div style="font-size:13px;color:var(--text-dim);margin-top:6px;">Performance charts and statistics will appear once trades are closed.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        closed_sorted_a = sorted(closed_a, key=lambda x: x["exit_date"])
        dates_a  = [str(t["exit_date"]) for t in closed_sorted_a]
        pnls_a   = [float(t["pnl"]) for t in closed_sorted_a]

        cumulative_a = []
        running_a = 0
        for p in pnls_a:
            running_a += p
            cumulative_a.append(running_a)

        # ── Cumulative P&L chart ──
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Cumulative Realised P&L</div>', unsafe_allow_html=True)

        fig_cum = go.Figure()
        is_positive = cumulative_a[-1] >= 0 if cumulative_a else True
        line_col  = "#00FF88" if is_positive else "#FF4757"
        fill_col  = "rgba(0,255,136,0.08)" if is_positive else "rgba(255,71,87,0.08)"

        fig_cum.add_trace(go.Scatter(
            x=dates_a, y=cumulative_a,
            mode="lines+markers",
            line=dict(color=line_col, width=2.5),
            marker=dict(color=line_col, size=5, line=dict(color="#080C14", width=1.5)),
            fill="tozeroy", fillcolor=fill_col,
            name="Cumulative P&L",
            hovertemplate="<b>%{x}</b><br>P&L: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_cum.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#64748B", family="Inter"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="₹", tickfont=dict(color="#94A3B8", size=11)),
            height=360, margin=dict(t=10,b=20,l=20,r=20),
            showlegend=False,
            hovermode="x unified",
        )
        fig_cum.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
        st.plotly_chart(fig_cum, use_container_width=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # ── Individual trade bars ──
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Individual Trade P&L</div>', unsafe_allow_html=True)
        bar_cols_a = ["#00FF88" if p >= 0 else "#FF4757" for p in pnls_a]
        fig_bars = go.Figure(go.Bar(
            x=dates_a, y=pnls_a,
            marker=dict(color=bar_cols_a, opacity=0.85, line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>P&L: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_bars.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#64748B", family="Inter"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="₹", tickfont=dict(color="#94A3B8", size=11)),
            height=300, margin=dict(t=10,b=20,l=20,r=20),
            showlegend=False,
        )
        fig_bars.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)", line_width=1)
        st.plotly_chart(fig_bars, use_container_width=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # ── Performance metrics ──
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Performance Metrics</div>', unsafe_allow_html=True)

        total_profit_a = float(summary.get("total_profit", 0))
        total_loss_a   = abs(float(summary.get("total_loss", 0)))
        wins_a         = int(summary.get("winning_trades", 0))
        losses_a       = int(summary.get("losing_trades", 0))
        avg_win_a      = total_profit_a / max(wins_a, 1)
        avg_loss_a     = total_loss_a / max(losses_a, 1)
        pf_a           = total_profit_a / total_loss_a if total_loss_a > 0 else float("inf")
        wr_a           = (wins_a / max(wins_a + losses_a, 1)) * 100
        ev_a           = (avg_win_a * (wr_a / 100)) - (avg_loss_a * (1 - wr_a / 100))
        roi_a          = (pnl / TOTAL_CAPITAL) * 100

        pm1, pm2, pm3, pm4 = st.columns(4)
        with pm1:
            st.markdown(f"""<div class="neon-card neon-card-green">
                <div class="neon-label">Total Profit</div>
                <div class="neon-value neon-green">₹{total_profit_a:,.0f}</div>
                <div class="neon-sub">{wins_a} winning trades</div>
            </div>""", unsafe_allow_html=True)
        with pm2:
            st.markdown(f"""<div class="neon-card neon-card-red">
                <div class="neon-label">Total Loss</div>
                <div class="neon-value neon-red">₹{total_loss_a:,.0f}</div>
                <div class="neon-sub">{losses_a} losing trades</div>
            </div>""", unsafe_allow_html=True)
        with pm3:
            pf_disp = f"{pf_a:.2f}" if pf_a != float("inf") else "∞"
            pf_cls  = "neon-card-green" if pf_a >= 1 else "neon-card-red"
            pf_vcls = "neon-green" if pf_a >= 1 else "neon-red"
            st.markdown(f"""<div class="neon-card {pf_cls}">
                <div class="neon-label">Profit Factor</div>
                <div class="neon-value {pf_vcls}">{pf_disp}</div>
                <div class="neon-sub">Gross profit / Gross loss</div>
            </div>""", unsafe_allow_html=True)
        with pm4:
            ev_cls  = "neon-card-green" if ev_a >= 0 else "neon-card-red"
            ev_vcls = "neon-green" if ev_a >= 0 else "neon-red"
            st.markdown(f"""<div class="neon-card {ev_cls}">
                <div class="neon-label">Expected Value</div>
                <div class="neon-value {ev_vcls}">{'+'if ev_a>=0 else ''}₹{ev_a:,.0f}</div>
                <div class="neon-sub">Per trade expectancy</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        # ── Historical Equity Curve ──
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Portfolio Equity Curve</div>', unsafe_allow_html=True)
        equity_history = get_equity_history(limit=90) if get_equity_history else []
        if equity_history:
            df_eq = pd.DataFrame(equity_history)
            
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=df_eq['log_date'], y=df_eq['equity'],
                mode='lines',
                fill="tozeroy", fillcolor="rgba(0, 212, 255, 0.1)",
                line=dict(color="#00D4FF", width=2.5),
                hovertemplate="<b>%{x}</b><br>Equity: ₹%{y:,.2f}<extra></extra>",
            ))
            fig_eq.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748B", family="Inter"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="₹", tickfont=dict(color="#94A3B8", size=11)),
                height=300, margin=dict(t=10,b=20,l=20,r=20),
                showlegend=False,
            )
            st.plotly_chart(fig_eq, use_container_width=True)
        else:
            st.info("No equity history available yet. The bot needs to run its daily routine to log equity.")
            
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        # ── Sector P&L + Drawdown ──
        col_sec, col_dd = st.columns(2)

        with col_sec:
            st.markdown('<div class="section-title"><span class="section-title-dot"></span> P&L by Sector</div>', unsafe_allow_html=True)
            sec_pnl = {}
            for t in closed_a:
                s = t["sector"] or "Unknown"
                sec_pnl[s] = sec_pnl.get(s, 0) + float(t["pnl"])
            secs  = list(sec_pnl.keys())
            svals = list(sec_pnl.values())
            scols = ["#00FF88" if v >= 0 else "#FF4757" for v in svals]

            fig_sec = go.Figure(go.Bar(
                x=secs, y=svals,
                marker=dict(color=scols, opacity=0.85, line=dict(width=0)),
                text=[f"₹{v:+,.0f}" for v in svals],
                textposition="outside",
                textfont=dict(family="JetBrains Mono", size=10, color="#E2E8F0"),
                hovertemplate="<b>%{x}</b><br>P&L: ₹%{y:,.2f}<extra></extra>",
            ))
            fig_sec.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748B", family="Inter"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="₹", tickfont=dict(color="#94A3B8", size=11)),
                height=340, margin=dict(t=10,b=20,l=20,r=20),
                showlegend=False,
            )
            fig_sec.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
            st.plotly_chart(fig_sec, use_container_width=True)

        with col_dd:
            st.markdown('<div class="section-title"><span class="section-title-dot"></span> Drawdown Analysis</div>', unsafe_allow_html=True)
            if len(cumulative_a) > 1:
                peak_dd = np.maximum.accumulate(cumulative_a)
                dd_pct  = ((np.array(cumulative_a) - peak_dd) / np.where(peak_dd == 0, 1, peak_dd)) * 100

                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=dates_a, y=dd_pct,
                    fill="tozeroy", fillcolor="rgba(255,71,87,0.12)",
                    line=dict(color="#FF4757", width=1.5),
                    hovertemplate="<b>%{x}</b><br>Drawdown: %{y:.2f}%<extra></extra>",
                ))
                fig_dd.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#64748B", family="Inter"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#94A3B8", size=11)),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", ticksuffix="%", tickfont=dict(color="#94A3B8", size=11)),
                    height=340, margin=dict(t=10,b=20,l=20,r=20),
                    showlegend=False,
                )
                st.plotly_chart(fig_dd, use_container_width=True)
            else:
                st.info("Need at least 2 closed trades for drawdown analysis.")

        # ── Stats table ──
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-title"><span class="section-title-dot"></span> Detailed Performance Summary</div>', unsafe_allow_html=True)

        stats_data = [
            {"Metric": "Total Realised P&L",   "Value": f"{'+'if pnl>=0 else ''}₹{pnl:,.2f}",         "Description": "Sum of all realized profits and losses"},
            {"Metric": "Total Profit",          "Value": f"₹{total_profit_a:,.2f}",                    "Description": "Gross profit from all winning trades"},
            {"Metric": "Total Loss",            "Value": f"₹{total_loss_a:,.2f}",                      "Description": "Gross loss from all losing trades"},
            {"Metric": "Avg Win per Trade",     "Value": f"₹{avg_win_a:,.2f}",                         "Description": "Average gain on profitable trades"},
            {"Metric": "Avg Loss per Trade",    "Value": f"₹{avg_loss_a:,.2f}",                        "Description": "Average drawdown on losing trades"},
            {"Metric": "Win Rate",              "Value": f"{wr_a:.1f}%",                               "Description": "Percentage of trades closed in profit"},
            {"Metric": "Profit Factor",         "Value": pf_disp,                                      "Description": "Gross profit ÷ Gross loss (>1 is profitable)"},
            {"Metric": "Expected Value",        "Value": f"{'+'if ev_a>=0 else ''}₹{ev_a:,.2f}",       "Description": "Statistical expectancy per trade"},
            {"Metric": "Return on Capital",     "Value": f"{'+'if roi_a>=0 else ''}{roi_a:.2f}%",      "Description": f"P&L as % of ₹{TOTAL_CAPITAL:,.0f} capital"},
        ]
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# TAB 4 — News & Logs
# ══════════════════════════════════════════════════════════
with tab4:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    col_date, col_btn = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input("Select date", value=date.today(), label_visibility="collapsed")
    with col_btn:
        if st.button("🔍 Fetch Live News"):
            try:
                from news_fetcher import NewsFetcher
                fetcher = NewsFetcher()
                news_text = fetcher.get_latest_indian_business_news(max_articles=10)
                if news_text:
                    st.session_state.last_news = news_text
                    st.success("Latest news fetched!")
                else:
                    st.warning("No news available")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="section-title-dot"></span> Market News Archive</div>', unsafe_allow_html=True)

    news = get_news_for_date(selected_date)
    if news:
        st.code(news, language="text")
    elif hasattr(st, "session_state") and "last_news" in st.session_state:
        st.code(st.session_state.last_news, language="text")
    else:
        st.markdown(f"""
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:24px;text-align:center;">
            <div style="color:var(--text-dim);font-size:13px;">No news stored for {selected_date}. The bot may not have run on this date, or click "Fetch Live News" to load current headlines.</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="section-title-dot"></span> Recent Trading Logs</div>', unsafe_allow_html=True)

    import os
    log_file = "logs/trading_bot.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
        recent = "".join(lines[-80:])
        st.code(recent, language="log")
    else:
        st.markdown("""
        <div style="background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:24px;text-align:center;">
            <div style="color:var(--text-dim);font-size:13px;">No log file found at <code>logs/trading_bot.log</code>. Logs appear after the first bot run.</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# TAB 5 — Settings
# ══════════════════════════════════════════════════════════
with tab5:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    import os
    from pathlib import Path

    # Locate the .env file (same directory as dashboard.py)
    _env_path = Path(__file__).parent / ".env"

    def _read_env() -> dict:
        """Read current .env values without crashing if file missing."""
        vals = {}
        if _env_path.exists():
            with open(_env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        vals[k.strip()] = v.strip().strip('"').strip("'")
        return vals

    def _write_env_key(key: str, value: str):
        """Write or update a single key in the .env file."""
        lines = []
        found = False
        if _env_path.exists():
            with open(_env_path) as f:
                lines = f.readlines()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                new_lines.append(f'{key}="{value}"\n')
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f'{key}="{value}"\n')
        with open(_env_path, "w") as f:
            f.writelines(new_lines)

    env = _read_env()

    # ── 1. Trading Parameters ──────────────────────────────────────────────
    st.markdown("""
    <div class="settings-section">
        <div class="settings-section-title">💰 Trading Parameters</div>
    </div>""", unsafe_allow_html=True)

    with st.container():
        with st.form("form_trading"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_capital = st.number_input(
                    "Total Capital (₹)",
                    min_value=1000.0, max_value=10_000_000.0, step=1000.0,
                    value=float(env.get("TOTAL_CAPITAL", "50000")),
                    help="The maximum amount allocated for this strategy. Controls position sizing."
                )
                new_risk_pct = st.number_input(
                    "Max Risk Per Trade (%)",
                    value=float(env.get("MAX_RISK_PER_TRADE_PCT", "0.005")) * 100, step=0.1
                ) / 100
                new_sl_pct = st.number_input(
                    "Stop Loss (%)",
                    value=float(env.get("STOP_LOSS_PCT", "0.05")) * 100, step=1.0
                ) / 100
            with col_b:
                new_live = st.selectbox(
                    "Trading Mode",
                    options=["PAPER (Safe — no real orders)", "LIVE (Real money — use with caution)"],
                    index=0 if env.get("LIVE_MODE", "False").lower() not in ("true","1","yes") else 1,
                    help="PAPER mode simulates orders. LIVE mode places real Zerodha orders."
                )
                new_tp_pct = st.number_input(
                    "Profit Target (%)",
                    value=float(env.get("PROFIT_TARGET_PCT", "0.15")) * 100, step=1.0
                ) / 100
                new_ts_pct = st.number_input(
                    "Trailing Stop (%)",
                    value=float(env.get("TRAILING_STOP_PCT", "0.03")) * 100, step=0.5
                ) / 100
            st.markdown('<div class="settings-hint">⚠️ Changing capital affects position sizing. Restart required for changes to take effect in the trading engine.</div>', unsafe_allow_html=True)
            if st.form_submit_button("💾  Save Trading Parameters"):
                _write_env_key("TOTAL_CAPITAL", str(new_capital))
                _write_env_key("LIVE_MODE", "True" if "LIVE" in new_live else "False")
                _write_env_key("MAX_RISK_PER_TRADE_PCT", str(new_risk_pct))
                _write_env_key("STOP_LOSS_PCT", str(new_sl_pct))
                _write_env_key("PROFIT_TARGET_PCT", str(new_tp_pct))
                _write_env_key("TRAILING_STOP_PCT", str(new_ts_pct))
                st.success("✅ Trading parameters saved to .env — restart the app to apply.")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── 2. AI Engine ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="settings-section">
        <div class="settings-section-title">🤖 AI Engine — Google Gemini</div>
    </div>""", unsafe_allow_html=True)

    with st.form("form_ai"):
        google_key = st.text_input(
            "GOOGLE_API_KEY (Gemini)",
            value=env.get("GOOGLE_API_KEY", ""),
            type="password",
            placeholder="AIza...",
            help="Get your free key at aistudio.google.com → Get API Key. Used for all BUY/SELL decisions."
        )
        col_x, col_y = st.columns(2)
        with col_x:
            xai_key = st.text_input("XAI_API_KEY (Grok — optional)", value=env.get("XAI_API_KEY",""), type="password", placeholder="xai-...")
        with col_y:
            oai_key = st.text_input("OPENAI_API_KEY (optional fallback)", value=env.get("OPENAI_API_KEY",""), type="password", placeholder="sk-...")
        st.markdown('<div class="settings-hint">💡 Only GOOGLE_API_KEY is required. Gemini 2.5 Flash is free (1,500 requests/day). Other keys are optional fallbacks.</div>', unsafe_allow_html=True)
        if st.form_submit_button("💾  Save AI Keys"):
            if google_key: _write_env_key("GOOGLE_API_KEY", google_key)
            if xai_key:    _write_env_key("XAI_API_KEY", xai_key)
            if oai_key:    _write_env_key("OPENAI_API_KEY", oai_key)
            st.success("✅ AI API keys saved.")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── 3. News API ────────────────────────────────────────────────────────
    st.markdown("""
    <div class="settings-section">
        <div class="settings-section-title">📰 News Source — NewsData.io</div>
    </div>""", unsafe_allow_html=True)

    with st.form("form_news"):
        news_key = st.text_input(
            "NEWS_API_KEY",
            value=env.get("NEWS_API_KEY", ""),
            type="password",
            placeholder="pub_...",
            help="Free at newsdata.io — up to 200 requests/day on the free plan."
        )
        st.markdown('<div class="settings-hint">📌 This key fetches the 15 latest Indian business headlines daily. Used to build the AI\'s market context.</div>', unsafe_allow_html=True)
        if st.form_submit_button("💾  Save News API Key"):
            if news_key: _write_env_key("NEWS_API_KEY", news_key)
            st.success("✅ News API key saved.")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── 4. Telegram Alerts ─────────────────────────────────────────────────
    st.markdown("""
    <div class="settings-section">
        <div class="settings-section-title">📲 Telegram Alerts</div>
    </div>""", unsafe_allow_html=True)

    with st.form("form_telegram"):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tg_token = st.text_input(
                "TELEGRAM_BOT_TOKEN",
                value=env.get("TELEGRAM_BOT_TOKEN", ""),
                type="password",
                placeholder="1234567890:AAH...",
                help="Create a bot via @BotFather on Telegram → /newbot"
            )
        with col_t2:
            tg_chat = st.text_input(
                "TELEGRAM_CHAT_ID",
                value=env.get("TELEGRAM_CHAT_ID", ""),
                placeholder="-100123456789",
                help="Message your bot, then visit api.telegram.org/bot{TOKEN}/getUpdates to find your chat ID"
            )
        st.markdown('<div class="settings-hint">📌 Get your Chat ID: message your bot first, then open <code>api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> — look for "chat"."id" in the response.</div>', unsafe_allow_html=True)

        col_sb, col_test = st.columns([2,1])
        with col_sb:
            save_tg = st.form_submit_button("💾  Save Telegram Settings")
        with col_test:
            test_tg = st.form_submit_button("🔔  Send Test Message")

        if save_tg:
            if tg_token: _write_env_key("TELEGRAM_BOT_TOKEN", tg_token)
            if tg_chat:  _write_env_key("TELEGRAM_CHAT_ID", tg_chat)
            st.success("✅ Telegram settings saved.")

        if test_tg:
            try:
                import requests as _req
                _tok = tg_token or env.get("TELEGRAM_BOT_TOKEN","")
                _cid = tg_chat  or env.get("TELEGRAM_CHAT_ID","")
                if _tok and _cid:
                    r = _req.post(
                        f"https://api.telegram.org/bot{_tok}/sendMessage",
                        json={"chat_id": _cid, "text": "⚡ *NiftyMind* — test message from Settings page ✅", "parse_mode":"Markdown"},
                        timeout=8
                    )
                    if r.json().get("ok"):
                        st.success("✅ Test message sent to Telegram!")
                    else:
                        st.error(f"Telegram error: {r.json().get('description')}")
                else:
                    st.warning("Enter both BOT_TOKEN and CHAT_ID first.")
            except Exception as e:
                st.error(f"Failed: {e}")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── 5. Zerodha / Kite ──────────────────────────────────────────────────
    st.markdown("""
    <div class="settings-section">
        <div class="settings-section-title">🏦 Zerodha Kite Connect</div>
    </div>""", unsafe_allow_html=True)

    with st.form("form_kite"):
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            kite_key = st.text_input("KITE_API_KEY", value=env.get("KITE_API_KEY",""), type="password", placeholder="your_api_key")
            kite_req = st.text_input("KITE_REQUEST_TOKEN", value=env.get("KITE_REQUEST_TOKEN",""), type="password", placeholder="refresh daily after login")
        with col_k2:
            kite_sec = st.text_input("KITE_API_SECRET", value=env.get("KITE_API_SECRET",""), type="password", placeholder="your_api_secret")
            kite_acc = st.text_input("KITE_ACCESS_TOKEN", value=env.get("KITE_ACCESS_TOKEN",""), type="password", placeholder="generated from request token")
        st.markdown('<div class="settings-hint">⚠️ Access tokens expire daily. In PAPER mode these are not required — the bot simulates all orders locally. Only needed for LIVE mode.</div>', unsafe_allow_html=True)
        if st.form_submit_button("💾  Save Kite Credentials"):
            if kite_key: _write_env_key("KITE_API_KEY", kite_key)
            if kite_sec: _write_env_key("KITE_API_SECRET", kite_sec)
            if kite_req: _write_env_key("KITE_REQUEST_TOKEN", kite_req)
            if kite_acc: _write_env_key("KITE_ACCESS_TOKEN", kite_acc)
            st.success("✅ Kite credentials saved.")

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── Current .env snapshot ──────────────────────────────────────────────
    with st.expander("🔍 View current .env snapshot (values masked)"):
        if _env_path.exists():
            masked_lines = []
            with open(_env_path) as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _, v = stripped.partition("=")
                        v_clean = v.strip().strip('"').strip("'")
                        if v_clean:
                            visible = v_clean[:4] + "●●●●●●" if len(v_clean) > 4 else "●●●●"
                        else:
                            visible = "(not set)"
                        masked_lines.append(f"{k.strip()} = {visible}")
                    else:
                        masked_lines.append(line.rstrip())
            st.code("\n".join(masked_lines), language="bash")
        else:
            st.warning(f".env file not found at {_env_path}. Save any setting above to create it.")


# ══════════════════════════════════════════════════════════
# TAB 6 — Backtest Lab
# ══════════════════════════════════════════════════════════
with tab6:
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title"><span class="section-title-dot"></span> AI Backtesting Engine</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="color:var(--text-dim);font-size:14px;margin-bottom:24px;">
    Run a historical simulation over the past N days. The engine fetches historical data via <code>yfinance</code> and uses the AI to simulate buying decisions, whilst strictly adhering to your configured trailing stops and stop losses.
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("backtest_form"):
        sim_days = st.slider("Simulation Range (Days)", min_value=7, max_value=90, value=30, step=7)
        run_sim = st.form_submit_button("🚀  Run Backtest Simulation")
        
    if run_sim:
        with st.spinner(f"Running {sim_days}-day backtest... This might take a minute."):
            try:
                from backtest_engine import run_backtest
                res = run_backtest(days=sim_days)
                
                if res.get("status") == "success":
                    metrics = res.get("metrics", {})
                    
                    st.success("✅ Backtest Complete!")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total Trades", metrics.get("total_trades", 0))
                    c2.metric("Win Rate", f"{metrics.get('win_rate', 0):.1f}%")
                    c3.metric("Total P&L", f"₹{metrics.get('total_pnl', 0):,.2f}")
                    c4.metric("Final Equity", f"₹{metrics.get('final_equity', 0):,.2f}")
                    
                    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
                    st.markdown('**Simulated Equity Curve**')
                    eq_data = res.get("equity_curve", [])
                    if eq_data:
                        df_eq = pd.DataFrame(eq_data)
                        fig_eq = px.line(df_eq, x="date", y="equity", template="plotly_dark")
                        fig_eq.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            margin=dict(t=10,b=10,l=10,r=10),
                            height=300
                        )
                        st.plotly_chart(fig_eq, use_container_width=True)
                        
                    st.markdown('**Simulated Trade History**')
                    th_data = res.get("trade_history", [])
                    if th_data:
                        st.dataframe(pd.DataFrame(th_data), use_container_width=True, hide_index=True)
                    else:
                        st.info("No trades were placed during the simulation period.")
                else:
                    st.error(f"Backtest Failed: {res.get('error')}")
            except Exception as e:
                st.error(f"Error during simulation: {e}")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    border-top: 1px solid rgba(255,255,255,0.06);
    padding: 16px 0;
    margin-top: 24px;
    display: flex;
    justify-content: center;
    gap: 24px;
    flex-wrap: wrap;
">
    <span style="font-size:12px;color:#334155;">⚡ NiftyMind</span>
    <span style="color:#1E293B;">·</span>
    <span style="font-size:12px;color:#334155;">NSE Delivery · Gemini 2.5 Flash</span>
    <span style="color:#1E293B;">·</span>
    <span style="font-size:12px;color:#334155;">Educational use only</span>
</div>
""", unsafe_allow_html=True)
