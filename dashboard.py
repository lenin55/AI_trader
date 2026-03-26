"""
Streamlit Dashboard for rupee50k-ai-sector-trader.
Displays live portfolio, open positions, trade history, P&L analytics,
and daily news/evaluation logs — all pulled from PostgreSQL.

Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np

from config import LIVE_MODE, MAX_RISK_PER_TRADE, TOTAL_CAPITAL

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rupee50k AI Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — modern dark trading aesthetic ────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@300;400;500&display=swap');

    :root {
        --bg-color: #0D1117;
        --bg-color-light: #161B22;
        --border-color: #21262D;
        --text-color: #C9D9E9;
        --text-color-light: #8B949E;
        --primary-color: #58A6FF;
        --primary-color-light: #A3D0FF;
        --accent-green: #2ECC71;
        --accent-red: #E74C3C;
        --font-family: 'Inter', sans-serif;
    }

    html, body, [class*="css"] {
        font-family: var(--font-family);
        background-color: var(--bg-color);
        color: var(--text-color);
    }
    .main { background-color: var(--bg-color); }
    h1, h2, h3 { font-family: var(--font-family); letter-spacing: -0.02em; font-weight: 700; }

    /* Glassmorphism Card Effect */
    .card {
        background: rgba(22, 27, 34, 0.6);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.3s ease, border 0.3s ease;
    }

    .card:hover {
        transform: translateY(-5px);
        border: 1px solid var(--primary-color);
    }

    /* Metric Containers */
    [data-testid="metric-container"] {
        background: var(--bg-color-light);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        padding: 16px;
        transition: all 0.3s ease-in-out;
    }

    [data-testid="metric-container"]:hover {
        border-color: var(--primary-color);
        box-shadow: 0 0 15px rgba(88, 166, 255, 0.25);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: var(--bg-color-light);
        border-right: 1px solid var(--border-color);
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--primary-color);
        color: var(--bg-color);
        font-weight: 600;
        border-radius: 8px;
        padding: 12px 24px;
        border: none;
        transition: all 0.3s ease;
        min-height: 44px; /* Minimum touch target height */
        font-size: 16px; /* Readable font size */
    }

    .stButton > button:hover {
        background-color: var(--primary-color-light);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(88, 166, 255, 0.2);
    }

    /* Enhance button touch targets on mobile */
    @media (max-width: 768px) {
        .stButton > button {
            min-height: 48px;
            font-size: 17px;
            width: 100%;
            margin: 5px 0;
        }
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: var(--text-color-light);
        padding: 12px 16px; /* Increased padding for better touch target */
        min-height: 48px; /* Minimum height for touch targets */
    }

    .stTabs [aria-selected="true"] {
        color: var(--primary-color) !important;
        border-bottom: 2px solid var(--primary-color) !important;
    }

    /* Dataframes */
    .stDataFrame {
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
    }

    /* Status badges and colors */
    .positive, .badge-profit, .badge-open { color: var(--accent-green); }
    .negative, .badge-loss { color: var(--accent-red); }
    .badge-closed { color: var(--text-color-light); }
    .badge-live { color: var(--accent-red); font-weight: 700; animation: pulse 1.5s infinite; }
    .badge-paper { color: var(--accent-green); font-weight: 700; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* Section headers */
    .section-label {
        font-size: 12px;
        letter-spacing: 0.15em;
        color: var(--text-color-light);
        text-transform: uppercase;
        margin-bottom: 12px;
        font-weight: 600;
    }

    /* Data Item for Sidebar Mode */
    .data-item {
        background: var(--bg-color-light);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }

    .data-title {
        font-size: 12px;
        color: var(--text-color-light);
        margin-bottom: 5px;
        text-transform: uppercase;
    }

    .data-value {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-color);
    }
    
    /* Enhanced Responsive Design */
    @media (max-width: 768px) {
        /* Column adjustments - make columns stack vertically */
        [data-testid="stColumn"] {
            width: 100% !important;
            margin-bottom: 15px;
        }
        
        /* Make columns full width on very small screens */
        [data-testid="stHorizontalBlock"] {
            flex-direction: column;
        }
        
        /* Sidebar adjustments */
        [data-testid="stSidebar"] {
            width: 100% !important;
            flex-wrap: wrap;
        }
        
        /* Hide sidebar on mobile by default, show with hamburger */
        [data-testid="stSidebar"][aria-expanded="false"] {
            display: none;
        }
        
        /* Main content takes full width when sidebar is collapsed */
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* Improve metric containers */
        [data-testid="metric-container"] {
            margin-bottom: 10px;
        }
        
        /* Make buttons more touch-friendly */
        .stButton > button {
            min-height: 44px;
            font-size: 16px;
        }
        
        /* Improve dataframe readability */
        .stDataFrame {
            font-size: 14px;
        }
        
        /* Adjust tab styling */
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 14px;
        }
        
        /* Improve spacing for form elements */
        .stSelectbox, .stDateInput, .stTextInput {
            margin-bottom: 15px;
        }
    }
    
    /* Additional enhancements for small screens */
    @media (max-width: 480px) {
        h1 {
            font-size: 1.8rem;
        }
        
        h2, h3 {
            font-size: 1.4rem;
        }
        
        /* Stack metrics vertically */
        .metric-row {
            flex-direction: column;
            gap: 10px;
        }
        
        /* Make cards take full width */
        .card {
            margin-left: 0 !important;
            margin-right: 0 !important;
        }
        
        /* Improve touch targets */
        .stCheckbox, .stRadio {
            padding: 10px;
        }
        
        /* Make tabs scrollable if overflow */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            overflow-x: auto;
            white-space: nowrap;
            padding-bottom: 10px;
        }
        
        .stTabs [data-baseweb="tab"] {
            min-width: 80px;
            white-space: nowrap;
        }
        
        /* Make charts more mobile-friendly */
        .js-plotly-plot {
            width: 100% !important;
            height: auto !important;
            min-height: 250px;
        }
        
        /* Improve table responsiveness */
        .stDataFrame {
            font-size: 13px;
        }
        
        .stDataFrame table {
            width: 100%;
            display: block;
            overflow-x: auto;
        }
        
        /* Reduce chart height on very small screens */
        .plotly {
            height: 200px !important;
        }
    }
    
    /* Enhancements for slightly larger mobile screens */
    @media (max-width: 768px) and (min-width: 481px) {
        .js-plotly-plot {
            min-height: 300px;
        }
        
        /* Adjust column layouts for better use of space */
        [data-testid="stColumn"] {
            padding: 0 5px;
        }
    }
</style>
""", unsafe_allow_html=True)


# ── Safe DB import (graceful if DB not configured yet) ─────────────────────────
def try_import_db():
    try:
        from database import (
            get_open_trades, get_trade_history,
            get_portfolio_summary, get_news_for_date,
            get_today_decision,
            initialize_database
        )
        initialize_database()
        return get_open_trades, get_trade_history, get_portfolio_summary, get_news_for_date, get_today_decision, None
    except Exception as e:
        return None, None, None, None, None, str(e)

(get_open_trades, get_trade_history,
 get_portfolio_summary, get_news_for_date, get_today_decision, db_error) = try_import_db()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Mobile hamburger menu button (hidden on desktop)
    st.markdown("""
    <div id="mobile-sidebar-toggle" style="display: none;">
        <button class="sidebar-toggle-btn" onclick="toggleSidebar()">
            ☰ Menu
        </button>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h3 style='text-align: center;'>🤖 Rupee50k AI Trader</h3>", unsafe_allow_html=True)
    st.markdown("---")

    mode_html = (
        '<div class="data-item"><div class="data-title">MODE</div><div class="data-value badge-live">LIVE</div></div>'
        if LIVE_MODE else
        '<div class="data-item"><div class="data-title">MODE</div><div class="data-value badge-paper">PAPER</div></div>'
    )
    st.markdown(mode_html, unsafe_allow_html=True)
    
    # Portfolio metrics in sidebar
    st.markdown('<p class="section-label">Portfolio Metrics</p>', unsafe_allow_html=True)
    summary = get_portfolio_summary() if not db_error else {}
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Capital", f"₹{TOTAL_CAPITAL:,.0f}")
        st.metric("Open Positions", summary.get("open_positions", 0))
    with col2:
        st.metric("Max Risk/Trade", f"₹{MAX_RISK_PER_TRADE:,.2f}")
        st.metric("Closed Trades", summary.get("closed_trades", 0))
    
    st.markdown("---")
    st.markdown('<p class="section-label">Risk Management</p>', unsafe_allow_html=True)
    st.markdown("**Stop-Loss:** 5%")
    st.markdown("**Profit Target:** 15%")

    st.markdown("---")
    st.markdown('<p class="section-label">Quick Actions</p>', unsafe_allow_html=True)

    if st.button("▶️ Execute Daily Analysis"):
        with st.spinner("Running AI analysis..."):
            try:
                from trading_logic import SectorTrader
                trader = SectorTrader()
                result = trader.execute_daily_routine()
                if result.get("status") == "success":
                    st.success(f"✅ Success: {result.get('action')}")
                else:
                    st.error(result.get("message", "Unknown error"))
            except Exception as e:
                st.error(f"❌ Error: {e}")

    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

    # Portfolio performance in sidebar
    if not db_error:
        pnl = float(summary.get("total_realised_pnl", 0))
        pnl_pct = (pnl / TOTAL_CAPITAL) * 100
        
        st.markdown("---")
        st.markdown('<p class="section-label">Performance</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='data-value {('positive' if pnl >= 0 else 'negative')}'>₹{pnl:,.2f}</div>", unsafe_allow_html=True)
            st.caption("Total P&L")
        with col2:
            st.markdown(f"<div class='data-value {('positive' if pnl_pct >= 0 else 'negative')}'>{pnl_pct:.2f}%</div>", unsafe_allow_html=True)
            st.caption("Return on Capital")


# ── Main area ──────────────────────────────────────────────────────────────────
st.markdown("<h1 style='text-align: center; font-size: 2.8rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #58A6FF, #A3D0FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>📈 NexGen AI Trading Terminal</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8b949e; margin-bottom: 40px; font-size: 1.1rem; letter-spacing: 0.5px;'>Institutional-Grade Algorithmic Execution strictly capped for retail.</p>", unsafe_allow_html=True)

if db_error:
    st.error(f"⚠️ Database not connected: `{db_error}`")
    st.info("Make sure `DATABASE_URL` is set in your `.env` file and PostgreSQL is running.")
    st.stop()

# ── Today's Market Macro Status ───────────────────────────────────────────────
today_decision = get_today_decision(date.today()) if get_today_decision else None

if today_decision:
    action = today_decision.get("action", "UNKNOWN")
    reason = today_decision.get("reason", "No reason provided.")
    
    # Modern styled status banner
    if action == "NO_TRADE":
        status_color = "#F39C12"
        bg_color = "rgba(243, 156, 18, 0.08)"
        border_color = "rgba(243, 156, 18, 0.4)"
        icon = "🛡️"
        action_text = "CAPITAL PRESERVATION MODE (NO TRADE)"
    elif action == "BUY":
        status_color = "#2ECC71"
        bg_color = "rgba(46, 204, 113, 0.08)"
        border_color = "rgba(46, 204, 113, 0.4)"
        icon = "🚀"
        action_text = "ACTIVE BUY SIGNAL GENERATED"
    else:
        status_color = "var(--primary-color)"
        bg_color = "rgba(88, 166, 255, 0.08)"
        border_color = "rgba(88, 166, 255, 0.4)"
        icon = "🔄"
        action_text = action

    st.markdown(f"""
    <div style="
        background: {bg_color}; 
        border: 1px solid {border_color};
        border-left: 6px solid {status_color};
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 40px;
        box-shadow: 0 8px 32px 0 rgba(0,0,0,0.15);
        backdrop-filter: blur(10px);
        transition: transform 0.3s ease;
    ">
        <h3 style="color: {status_color}; margin-top:0; margin-bottom:12px; font-weight: 800; letter-spacing: 1px; font-size: 1.4rem;">
            {icon} TODAY'S MACRO VERDICT: {action_text}
        </h3>
        <p style="color: var(--text-color); font-size: 1.05rem; margin: 0; line-height: 1.6;">
            <strong style="color: {status_color};">AI Thesis:</strong> {reason}
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("💡 The AI has not evaluated the market for today yet. Run the analysis from the sidebar.")


# ── Portfolio Summary KPIs ─────────────────────────────────────────────────────
summary = get_portfolio_summary()
open_trades_data = get_open_trades()

col1, col2, col3, col4, col5 = st.columns(5)

# Wrap each metric in the custom data-testid style by using raw HTML for ultra-responsive styling
with col1:
    st.markdown('<p class="section-label">Open Positions</p>', unsafe_allow_html=True)
    st.metric(label="Holdings", value=summary.get("open_positions", 0))
with col2:
    st.markdown('<p class="section-label">Closed Trades</p>', unsafe_allow_html=True)
    st.metric(label="Total Executed", value=summary.get("closed_trades", 0))
with col3:
    pnl = float(summary.get("total_realised_pnl", 0))
    st.markdown('<p class="section-label">Realised P&L</p>', unsafe_allow_html=True)
    st.markdown(f"<h3 class='{('positive' if pnl >= 0 else 'negative')}'>₹{pnl:,.2f}</h3>", unsafe_allow_html=True)
with col4:
    wins  = int(summary.get("winning_trades", 0))
    total = int(summary.get("closed_trades", 0) or 1)
    win_rate = (wins / total) * 100
    st.markdown('<p class="section-label">Win Accuracy</p>', unsafe_allow_html=True)
    st.metric(label="Win Rate", value=f"{win_rate:.1f}%", delta=f"{wins}W / {total - wins}L")
with col5:
    pnl_pct = (pnl / TOTAL_CAPITAL) * 100
    st.markdown('<p class="section-label">Gross Return</p>', unsafe_allow_html=True)
    st.metric(label="ROI", value=f"{pnl_pct:.2f}%")

st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
# Mobile-friendly tab labels with icons only for better touch targets
tab1, tab2, tab3, tab4 = st.tabs([
    "💼 Positions",
    "📋 History", 
    "📊 Analytics",
    "📰 News"
])


# ════════════════════════════════════════════════════════
# TAB 1 — Open Positions
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Current Portfolio Positions")
    
    if not open_trades_data:
        st.info("No open positions. The bot is fully in cash today.")
    else:
        from kite_client import KiteClient
        kite = KiteClient()

        rows = []
        total_current_value = 0
        total_entry_value = 0
        
        for t in open_trades_data:
            entry  = float(t["entry_price"])
            qty    = int(t["quantity"])
            ltp    = kite.get_ltp(t["stock"])
            pnl    = (ltp - entry) * qty
            pnl_pct = ((ltp - entry) / entry) * 100
            sl_price = entry * 0.95
            tp_price = entry * 1.15
            
            current_value = ltp * qty
            entry_value = entry * qty
            
            rows.append({
                "Stock":        t["stock"],
                "Sector":       t["sector"] or "—",
                "Qty":          qty,
                "Entry ₹":      f"₹{entry:,.2f}",
                "LTP ₹":        f"₹{ltp:,.2f}",
                "P&L ₹":        f"₹{pnl:,.2f}",
                "P&L %":        f"{pnl_pct:+.2f}%",
                "Stop-Loss":    f"₹{sl_price:,.2f}",
                "Target":       f"₹{tp_price:,.2f}",
                "Entry Date":   str(t["entry_date"]),
                "Days Held":    (date.today() - t["entry_date"]).days,
                "Current Value": f"₹{current_value:,.2f}",
                "Unrealized P&L": pnl,
                "Unrealized P&L %": pnl_pct
            })
            
            total_current_value += current_value
            total_entry_value += entry_value

        df = pd.DataFrame(rows)
        
        # Display portfolio summary card
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Positions Count", len(open_trades_data))
        with col2:
            total_unrealized = sum(row["Unrealized P&L"] for row in rows)
            st.metric("Total Unrealized P&L", f"₹{total_unrealized:,.2f}")
        with col3:
            st.metric("Total Current Value", f"₹{total_current_value:,.2f}")
        with col4:
            overall_pct = ((total_current_value - total_entry_value) / total_entry_value) * 100 if total_entry_value > 0 else 0
            st.metric("Overall Return", f"{overall_pct:+.2f}%")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Data grid for positions
        st.markdown("### Position Details")
        st.dataframe(df[[
            "Stock", "Sector", "Qty", "Entry ₹", "LTP ₹", "P&L ₹", "P&L %", 
            "Stop-Loss", "Target", "Days Held"
        ]].style.format({
            "Entry ₹": "₹{:,.2f}",
            "LTP ₹": "₹{:,.2f}",
            "P&L ₹": "₹{:,.2f}",
            "Stop-Loss": "₹{:,.2f}",
            "Target": "₹{:,.2f}",
            "P&L %": "{:+.2f}%"
        }), use_container_width=True, hide_index=True)

        # Per-position P&L chart
        if rows:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Add P&L bars
            pnl_values = [r["Unrealized P&L"] for r in rows]
            stock_names = [r["Stock"] for r in rows]
            colors = ["var(--accent-green)" if val >= 0 else "var(--accent-red)" for val in pnl_values]
            
            fig.add_trace(
                go.Bar(x=stock_names, y=pnl_values, marker_color=colors, name="P&L"),
            )
            
            # Add P&L % line
            pnl_pct_values = [r["Unrealized P&L %"] for r in rows]
            fig.add_trace(
                go.Scatter(x=stock_names, y=pnl_pct_values, mode='lines+markers', name="P&L %", line=dict(color="var(--primary-color)")),
                secondary_y=True,
            )
            
            fig.update_layout(
                title="Unrealised P&L per Position",
                paper_bgcolor="transparent", plot_bgcolor="transparent",
                font=dict(color="var(--text-color)", family="Inter"),
                xaxis=dict(gridcolor="var(--border-color)"),
                yaxis=dict(gridcolor="var(--border-color)", tickprefix="₹"),
                yaxis2=dict(gridcolor="var(--border-color)", tickprefix="+", side="right"),
                height=400,
            )
            fig.update_yaxes(title_text="P&L (₹)", secondary_y=False)
            fig.update_yaxes(title_text="P&L (%)", secondary_y=True)
            
            st.plotly_chart(fig, use_container_width=True)

        # Show today's AI evaluations if available
        st.markdown("### Today's AI Evaluations")
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
                for i, ev in enumerate(evals):
                    verdict_color = "🟢" if ev["ai_verdict"] == "HOLD" else "🔴"
                    with st.expander(f"{verdict_color} {ev['stock']} — {ev['ai_verdict']} (thesis intact: {ev['thesis_intact']})"):
                        st.write(f"**Current Price**: ₹{ev['current_price']:,.2f}")
                        st.write(f"**P&L**: ₹{ev['current_pnl']:,.2f} ({ev['pnl_pct']:+.2f}%)")
                        st.write("**AI Reasoning:**")
                        st.write(ev["ai_reasoning"])
            else:
                st.caption("No evaluations recorded yet for today.")
        except Exception as e:
            st.caption(f"Could not load evaluations: {e}")


# ════════════════════════════════════════════════════════
# TAB 2 — Trade History
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Completed Trade History")
    
    history = get_trade_history(limit=100)
    if not history:
        st.info("No closed trades yet.")
    else:
        rows = []
        for t in history:
            pnl = float(t["pnl"]) if t["pnl"] else 0
            rows.append({
                "ID":           t["id"],
                "Stock":        t["stock"],
                "Sector":       t["sector"] or "—",
                "Qty":          t["quantity"],
                "Entry ₹":      f"₹{float(t['entry_price']):,.2f}",
                "Exit ₹":       f"₹{float(t['exit_price']):,.2f}" if t["exit_price"] else "—",
                "P&L ₹":        f"₹{pnl:,.2f}",
                "Exit Reason":  t["exit_reason"] or "—",
                "Entry Date":   str(t["entry_date"]),
                "Exit Date":    str(t["exit_date"]) if t["exit_date"] else "OPEN",
                "Status":       t["status"],
                "P&L Num":      pnl
            })

        df_hist = pd.DataFrame(rows)

        # Colour-code P&L column
        def style_pnl(val):
            try:
                num = float(str(val).replace("₹", "").replace(",", ""))
                color = "#2ECC71" if num > 0 else ("#E74C3C" if num < 0 else "#8B949E")
                return f"color: {color}; font-weight: 600"
            except:
                return ""

        styled = df_hist[[
            "ID", "Stock", "Sector", "Qty", "Entry ₹", "Exit ₹", "P&L ₹", 
            "Exit Reason", "Entry Date", "Exit Date", "Status"
        ]].style.applymap(style_pnl, subset=["P&L ₹"])
        
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Charts section
        col1, col2 = st.columns(2)
        
        with col1:
            # Exit reason breakdown
            reason_counts = df_hist["Exit Reason"].value_counts().reset_index()
            reason_counts.columns = ["Reason", "Count"]
            fig_pie = px.pie(
                reason_counts, values="Count", names="Reason",
                title="Exit Reason Distribution",
                color_discrete_sequence=["var(--accent-green)", "var(--accent-red)", "#FFA500", "var(--primary-color)", "#E3B341"]
            )
            fig_pie.update_layout(
                paper_bgcolor="transparent",
                font=dict(color="var(--text-color)", family="Inter"),
                height=400,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Win/Loss distribution
            win_loss = df_hist[df_hist["P&L ₹"] != "₹0.00"]
            win_loss["Win/Loss"] = win_loss["P&L Num"].apply(lambda x: "Win" if x > 0 else "Loss")
            win_loss_counts = win_loss["Win/Loss"].value_counts().reset_index()
            win_loss_counts.columns = ["Result", "Count"]
            
            fig_bar = px.bar(
                win_loss_counts, 
                x="Result", 
                y="Count", 
                title="Win vs Loss Distribution",
                color="Result",
                color_discrete_map={"Win": "var(--accent-green)", "Loss": "var(--accent-red)"}
            )
            fig_bar.update_layout(
                paper_bgcolor="transparent",
                plot_bgcolor="transparent",
                font=dict(color="var(--text-color)", family="Inter"),
                height=400,
            )
            st.plotly_chart(fig_bar, use_container_width=True)


# ════════════════════════════════════════════════════════
# TAB 3 — P&L Analytics
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Advanced Performance Analytics")
    
    history = get_trade_history(limit=200)
    closed  = [t for t in history if t["status"] == "CLOSED" and t["pnl"] is not None]

    if not closed:
        st.info("No closed trades to analyse yet.")
    else:
        # Prepare data for analysis
        closed_sorted = sorted(closed, key=lambda x: x["exit_date"])
        dates  = [str(t["exit_date"]) for t in closed_sorted]
        pnls   = [float(t["pnl"]) for t in closed_sorted]
        
        # Calculate cumulative P&L
        cumulative = []
        running = 0
        for p in pnls:
            running += p
            cumulative.append(running)

        # Create combined chart with multiple metrics
        fig_combined = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=("Cumulative Realised P&L", "Individual Trade P&L"),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        # Add cumulative P&L
        fig_combined.add_trace(
            go.Scatter(
                x=dates, y=cumulative,
                mode="lines+markers",
                line=dict(color="var(--primary-color)", width=3),
                marker=dict(color="var(--primary-color)", size=6),
                fill="tonexty",
                fillcolor="rgba(88, 166, 255, 0.1)",
                name="Cumulative P&L"
            ),
            row=1, col=1
        )
        
        # Add individual trade P&L
        colors = ["var(--accent-green)" if p >= 0 else "var(--accent-red)" for p in pnls]
        fig_combined.add_trace(
            go.Bar(
                x=dates, y=pnls,
                marker_color=colors,
                name="Trade P&L"
            ),
            row=2, col=1
        )
        
        fig_combined.update_layout(
            title="P&L Performance Overview",
            paper_bgcolor="transparent", 
            plot_bgcolor="transparent",
            font=dict(color="var(--text-color)", family="Inter"),
            height=700,
        )
        
        fig_combined.update_xaxes(title_text="Date", row=2, col=1)
        fig_combined.update_yaxes(title_text="₹", row=1, col=1)
        fig_combined.update_yaxes(title_text="₹", row=2, col=1)
        
        st.plotly_chart(fig_combined, use_container_width=True)

        # Performance metrics grid
        st.markdown("### Performance Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        total_profit = float(summary.get("total_profit", 0))
        total_loss = abs(float(summary.get("total_loss", 0)))
        avg_win = total_profit / max(int(summary.get("winning_trades", 1)), 1)
        avg_loss = total_loss / max(int(summary.get("losing_trades", 1)), 1) if total_loss > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        with col1:
            st.metric("Total Profit", f"₹{total_profit:,.2f}")
        with col2:
            st.metric("Total Loss", f"₹{total_loss:,.2f}")
        with col3:
            st.metric("Profit Factor", f"{profit_factor:.2f}")
        with col4:
            st.metric("Expected Value", f"₹{(avg_win * (win_rate/100)) - (avg_loss * (1-(win_rate/100))):,.2f}")

        # Additional analytics
        col_a, col_b = st.columns(2)

        # Sector performance
        with col_a:
            sektor_pnl = {}
            for t in closed:
                sec = t["sector"] or "Unknown"
                sektor_pnl[sec] = sektor_pnl.get(sec, 0) + float(t["pnl"])

            sectors = list(sektor_pnl.keys())
            pnl_values = list(sektor_pnl.values())
            colors = ["var(--accent-green)" if v >= 0 else "var(--accent-red)" for v in pnl_values]

            fig_sec = go.Figure(go.Bar(
                x=sectors,
                y=pnl_values,
                marker_color=colors,
            ))
            fig_sec.update_layout(
                title="P&L by Sector",
                paper_bgcolor="transparent", 
                plot_bgcolor="transparent",
                font=dict(color="var(--text-color)", family="Inter"),
                xaxis=dict(gridcolor="var(--border-color)"),
                yaxis=dict(gridcolor="var(--border-color)", tickprefix="₹"),
                height=400,
            )
            st.plotly_chart(fig_sec, use_container_width=True)

        # Drawdown analysis
        with col_b:
            # Calculate drawdowns
            peak = np.maximum.accumulate(cumulative)
            drawdown = np.array(cumulative) - peak
            drawdown_pct = (drawdown / peak) * 100
            
            fig_dd = go.Figure()
            fig_dd.add_trace(
                go.Scatter(
                    x=dates,
                    y=drawdown_pct,
                    fill='tozeroy',
                    fillcolor='rgba(231, 76, 60, 0.3)',
                    line=dict(color='var(--accent-red)'),
                    name='Drawdown (%)'
                )
            )
            fig_dd.update_layout(
                title="Historical Drawdown (%)",
                paper_bgcolor="transparent", 
                plot_bgcolor="transparent",
                font=dict(color="var(--text-color)", family="Inter"),
                xaxis=dict(gridcolor="var(--border-color)"),
                yaxis=dict(gridcolor="var(--border-color)", tickprefix="", ticksuffix="%"),
                height=400,
            )
            st.plotly_chart(fig_dd, use_container_width=True)

        # Detailed stats table
        st.markdown("### Detailed Performance Summary")
        stats_df = pd.DataFrame([{
            "Metric": "Total Realised P&L",   
            "Value": f"₹{pnl:,.2f}",
            "Description": "Sum of all realized profits and losses"
        }, {
            "Metric": "Total Profit",          
            "Value": f"₹{total_profit:,.2f}",
            "Description": "Sum of all profitable trades"
        }, {
            "Metric": "Total Loss",            
            "Value": f"₹{total_loss:,.2f}",
            "Description": "Sum of all losing trades (absolute value)"
        }, {
            "Metric": "Average Win per Trade",     
            "Value": f"₹{avg_win:,.2f}",
            "Description": "Average profit on winning trades"
        }, {
            "Metric": "Average Loss per Trade",    
            "Value": f"₹{avg_loss:,.2f}",
            "Description": "Average loss on losing trades"
        }, {
            "Metric": "Win Rate",              
            "Value": f"{win_rate:.1f}%",
            "Description": "Percentage of winning trades"
        }, {
            "Metric": "Profit Factor",              
            "Value": f"{profit_factor:.2f}",
            "Description": "Gross profit / Gross loss"
        }, {
            "Metric": "Return on Capital",     
            "Value": f"{pnl_pct:.2f}%",
            "Description": "Total P&L as percentage of capital"
        }])
        
        st.dataframe(stats_df, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════
# TAB 4 — News Log
# ════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Market Insights & News Archive")
    
    # Date selection
    col_date, col_btn = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input("Select date", value=date.today())
    with col_btn:
        st.write("")  # Spacer
        if st.button("🔍 Fetch Latest News"):
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
                st.error(f"Error fetching news: {e}")

    # Display news for selected date
    news = get_news_for_date(selected_date)
    if news:
        st.markdown(f"#### News for {selected_date}")
        st.code(news, language="text")
    elif hasattr(st, 'session_state') and 'last_news' in st.session_state:
        st.markdown("#### Recently Fetched News")
        st.code(st.session_state.last_news, language="text")
    else:
        st.info(f"No news stored for {selected_date}. The bot may not have run that day.")

    # Show last 7 days of logs
    st.markdown("---")
    st.markdown("### Recent Trading Logs")
    import os
    log_file = "logs/trading_bot.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
        recent = "".join(lines[-60:])
        st.code(recent, language="log")
    else:
        st.caption("No log file found. Ensure logging is enabled in your configuration.")

st.markdown("---")
st.markdown('<p style="text-align: center; color: #8b949e;">Rupee50k AI Sector Trader · Conservative NSE delivery bot · For educational purposes only.</p>', unsafe_allow_html=True)

# Mobile sidebar toggle script
st.markdown("""
<script>
function toggleSidebar() {
    const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
        // Toggle aria-expanded attribute for accessibility
        const isExpanded = sidebar.getAttribute('aria-expanded') === 'true' || false;
        sidebar.setAttribute('aria-expanded', !isExpanded);
    }
}

// Add some CSS for the toggle button
const style = document.createElement('style');
style.textContent = `
    .sidebar-toggle-btn {
        background-color: var(--primary-color);
        color: var(--bg-color);
        font-weight: 600;
        border-radius: 8px;
        padding: 12px 24px;
        border: none;
        width: 100%;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .sidebar-toggle-btn:hover {
        background-color: var(--primary-color-light);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(88, 166, 255, 0.2);
    }
    
    /* Show mobile sidebar toggle on small screens */
    @media (max-width: 768px) {
        #mobile-sidebar-toggle {
            display: block !important;
        }
        
        /* Hide toggle when sidebar is expanded on desktop */
        @media (min-width: 769px) {
            #mobile-sidebar-toggle {
                display: none !important;
            }
        }
    }
`;
document.head.appendChild(style);

// Auto-collapse sidebar on mobile when clicking outside
document.addEventListener('click', function(event) {
    const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
    const toggleButton = window.parent.document.querySelector('.sidebar-toggle-btn');
    if (sidebar && toggleButton && !sidebar.contains(event.target) && !toggleButton.contains(event.target)) {
        if (!sidebar.classList.contains('collapsed')) {
            sidebar.classList.add('collapsed');
            sidebar.setAttribute('aria-expanded', 'false');
        }
    }
});
</script>
""", unsafe_allow_html=True)