"""
AI Backtesting Engine for NiftyNinety.
Runs a historical simulation using yfinance for price data
and Gemini to mock historical sentiment/decisions if real news is unavailable.
"""

import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import Dict, List, Any

from config import logger, TOTAL_CAPITAL, LIQUID_UNIVERSE, STOP_LOSS_PCT, PROFIT_TARGET_PCT, TRAILING_STOP_PCT
from ai_decision import AIDecisionMaker

def run_backtest(days: int = 30) -> Dict[str, Any]:
    logger.info(f"Starting {days}-day backtest simulation.")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Pre-fetch historical data for the universe
    logger.info("Fetching historical data from yfinance...")
    historical_data = {}
    for stock in LIQUID_UNIVERSE:
        ticker = f"{stock}.NS"
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not df.empty:
                historical_data[stock] = df
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            
    if not historical_data:
        return {"error": "Failed to fetch any historical data."}
        
    ai_maker = AIDecisionMaker()
    
    portfolio_cash = TOTAL_CAPITAL
    open_positions = []
    trade_history = []
    daily_equity = []
    
    # We will simulate trading days by taking the union of all dates
    all_dates = set()
    for df in historical_data.values():
        all_dates.update(df.index.date)
    
    sorted_dates = sorted(list(all_dates))
    
    for current_date in sorted_dates:
        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"--- Simulating Date: {date_str} ---")
        
        # 1. Exit Logic (Evaluate stops using today's High/Low)
        for pos in open_positions[:]:
            stock = pos["stock"]
            df = historical_data.get(stock)
            if df is None or current_date not in df.index:
                continue
                
            day_data = df.loc[current_date]
            high = float(day_data["High"].iloc[0])
            low = float(day_data["Low"].iloc[0])
            close = float(day_data["Close"].iloc[0])
            
            # Update highest seen price
            if high > pos["highest_price"]:
                pos["highest_price"] = high
                
            exit_price = None
            exit_reason = None
            
            # Check Stop Loss (Did low go below SL?)
            sl_price = pos["entry_price"] * (1 - STOP_LOSS_PCT)
            tp_price = pos["entry_price"] * (1 + PROFIT_TARGET_PCT)
            ts_price = pos["highest_price"] * (1 - TRAILING_STOP_PCT)
            
            if low <= sl_price:
                exit_price = sl_price
                exit_reason = "STOP_LOSS"
            elif high >= tp_price:
                exit_price = tp_price
                exit_reason = "PROFIT_TARGET"
            elif low <= ts_price:
                exit_price = ts_price
                exit_reason = "TRAILING_STOP"
                
            if exit_price:
                pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
                portfolio_cash += (exit_price * pos["quantity"])
                trade_history.append({
                    "stock": stock,
                    "entry_date": pos["entry_date"],
                    "entry_price": pos["entry_price"],
                    "exit_date": current_date,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl": pnl,
                    "quantity": pos["quantity"]
                })
                open_positions.remove(pos)
                logger.info(f"SOLD {stock} at {exit_price:.2f} ({exit_reason}) | P&L: {pnl:.2f}")

        # 2. Buy Logic
        # Mocking news since historical news APIs are limited on free tiers
        mock_news = f"General market update for India on {date_str}. Markets showing mixed sentiment. Some sectors performing well, others lagging."
        
        # Get decision
        decision = ai_maker.get_decision(news_text=mock_news, ta_context="Simulated backtest context.", sentiment_context="Neutral")
        action = decision.get("action", "NO_TRADE")
        recs = decision.get("recommendations", [])
        
        if action == "BUY" and recs:
            for rec in recs:
                stock = rec.get("stock")
                if any(p["stock"] == stock for p in open_positions):
                    continue # duplicate guard
                    
                df = historical_data.get(stock)
                if df is None or current_date not in df.index:
                    continue
                    
                close = float(df.loc[current_date]["Close"].iloc[0])
                
                # Sizing
                risk_per_share = close * STOP_LOSS_PCT
                max_risk = TOTAL_CAPITAL * float(eval(open(".env").read().split("MAX_RISK_PER_TRADE_PCT=")[1].split("\\n")[0]) if "MAX_RISK_PER_TRADE_PCT" in open(".env").read() else 0.005)
                allowed_qty_by_risk = int(max_risk // risk_per_share)
                allowed_qty_by_funds = int(portfolio_cash // close)
                qty = min(allowed_qty_by_risk, allowed_qty_by_funds)
                
                if qty > 0:
                    portfolio_cash -= (qty * close)
                    open_positions.append({
                        "stock": stock,
                        "entry_date": current_date,
                        "entry_price": close,
                        "highest_price": close,
                        "quantity": qty
                    })
                    logger.info(f"BOUGHT {qty} of {stock} at {close:.2f}")
                    
        # Log daily equity
        open_val = 0
        for pos in open_positions:
            df = historical_data.get(pos["stock"])
            if df is not None and current_date in df.index:
                open_val += float(df.loc[current_date]["Close"].iloc[0]) * pos["quantity"]
            else:
                open_val += pos["entry_price"] * pos["quantity"]
                
        daily_equity.append({
            "date": current_date,
            "equity": portfolio_cash + open_val
        })
        
    # Compile results
    total_trades = len(trade_history)
    wins = len([t for t in trade_history if t["pnl"] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    total_pnl = sum([t["pnl"] for t in trade_history])
    
    return {
        "status": "success",
        "equity_curve": daily_equity,
        "trade_history": trade_history,
        "metrics": {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "final_equity": daily_equity[-1]["equity"] if daily_equity else TOTAL_CAPITAL
        }
    }
