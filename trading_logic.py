"""
Trading Logic Module for rupee50k-ai-sector-trader.
Orchestrates the full daily routine:
  1. Exit checks on all open positions (stop-loss, profit target, AI thesis re-eval)
  2. BUY decision for today if no conflicting position exists
  3. Full persistence to PostgreSQL for every action
"""

from datetime import date
from typing import Dict, Any

from kite_client import KiteClient
from news_fetcher import NewsFetcher
from ai_decision import AIDecisionMaker
from sell_logic import SellEngine
from database import (
    initialize_database,
    insert_trade,
    log_daily_news,
    log_daily_decision,
    already_holds_stock,
    get_portfolio_summary,
)
from config import MAX_RISK_PER_TRADE, TOTAL_CAPITAL, logger

ASSUMED_SL_PERCENT = 0.05  # Used for quantity sizing (matches sell stop-loss threshold)


class SectorTrader:

    def __init__(self):
        # Ensure all DB tables exist on first run
        initialize_database()

        self.kite         = KiteClient()
        self.news_fetcher = NewsFetcher()
        self.ai           = AIDecisionMaker()
        self.sell_engine  = SellEngine(kite_client=self.kite, ai_maker=self.ai)

    def execute_daily_routine(self) -> Dict[str, Any]:
        logger.info("=== STARTING DAILY TRADING ROUTINE ===")

        # -------------------------------------------------------
        # 0. Check available funds
        # -------------------------------------------------------
        available_funds = self.kite.get_available_funds()
        if available_funds < 1000:
            logger.critical(f"Insufficient funds: ₹{available_funds}")
            return {"status": "error", "message": "Insufficient funds."}

        # -------------------------------------------------------
        # 1. Fetch today's news (once — shared by buy and sell logic)
        # -------------------------------------------------------
        news_text = self.news_fetcher.get_latest_indian_business_news(max_articles=15)
        today = date.today()

        # Persist news snapshot to DB
        article_count = news_text.count("Article ") if news_text else 0
        log_daily_news(log_date=today, news_text=news_text, article_count=article_count)
        logger.info(f"News snapshot ({article_count} articles) saved to DB for {today}.")

        # -------------------------------------------------------
        # 2. Run exit checks on ALL open positions FIRST
        # -------------------------------------------------------
        exit_events = self.sell_engine.run_daily_exit_checks(news_text=news_text)
        if exit_events:
            for event in exit_events:
                logger.info(
                    f"EXIT EVENT: {event.get('stock')} | "
                    f"Reason: {event.get('exit_reason')} | "
                    f"P&L: ₹{event.get('pnl')}"
                )

        # -------------------------------------------------------
        # 3. Get AI BUY decision for today
        # -------------------------------------------------------
        decision = self.ai.get_decision(news_text)
        action   = decision.get("action", "NO_TRADE")
        stock    = decision.get("stock", "None")
        reason   = decision.get("reason", "No reason.")
        sector   = decision.get("sector", "None")

        logger.info(f"AI suggests {action} for {stock}.")

        # Persist the macro decision for the dashboard to display
        log_daily_decision(decision_date=today, action=action, reason=reason)

        if action != "BUY" or stock in ("None", None, "NO_TRADE"):
            logger.info("No new trade taken today. Preserving capital.")
            return {
                "status":       "success",
                "action":       "NO_TRADE",
                "reason":       reason,
                "exit_events":  exit_events,
                "portfolio":    get_portfolio_summary(),
            }

        # -------------------------------------------------------
        # 4. Duplicate position guard
        # -------------------------------------------------------
        if already_holds_stock(stock):
            logger.warning(
                f"Already holding an open position in {stock}. "
                f"Skipping new BUY to avoid overexposure."
            )
            return {
                "status":      "success",
                "action":      "NO_TRADE",
                "reason":      f"Duplicate position guard: already hold {stock}.",
                "exit_events": exit_events,
                "portfolio":   get_portfolio_summary(),
            }

        # -------------------------------------------------------
        # 5. Calculate position size
        # -------------------------------------------------------
        ltp = self.kite.get_ltp(stock)
        if ltp <= 0:
            logger.error(f"Invalid LTP for {stock}. Aborting BUY.")
            return {"status": "error", "message": "Invalid LTP."}

        risk_per_share       = ltp * ASSUMED_SL_PERCENT
        allowed_qty_by_risk  = int(MAX_RISK_PER_TRADE // risk_per_share)
        max_capital_for_trade = min(available_funds, TOTAL_CAPITAL)
        allowed_qty_by_funds = int(max_capital_for_trade // ltp)
        final_qty            = min(allowed_qty_by_risk, allowed_qty_by_funds)

        if final_qty <= 0:
            logger.warning(f"Calculated qty is 0 for {stock} at ₹{ltp}. Stock too expensive for risk cap.")
            return {"status": "error", "message": "Calculated quantity is 0."}

        logger.info(
            f"Sizing: {final_qty} shares of {stock} @ ₹{ltp} "
            f"| Trade value: ₹{final_qty * ltp:.2f} "
            f"| Max risk: ₹{MAX_RISK_PER_TRADE:.2f}"
        )

        # -------------------------------------------------------
        # 6. Place BUY order
        # -------------------------------------------------------
        order_result = self.kite.place_buy_order(symbol=stock, quantity=final_qty)

        if order_result.get("status") != "success":
            logger.error(f"BUY order failed: {order_result.get('message')}")
            return {"status": "error", "message": order_result.get("message", "Order failed.")}

        # -------------------------------------------------------
        # 7. Persist trade to PostgreSQL
        # -------------------------------------------------------
        trade_id = insert_trade(
            stock=stock,
            sector=sector,
            quantity=final_qty,
            entry_price=ltp,
            entry_date=today,
            entry_thesis=reason,
            order_id=order_result.get("order_id", "unknown"),
        )
        logger.info(f"Trade #{trade_id} persisted to DB: BUY {final_qty} x {stock} @ ₹{ltp}")

        return {
            "status":       "success",
            "action":       "BUY",
            "trade_id":     trade_id,
            "stock":        stock,
            "sector":       sector,
            "quantity":     final_qty,
            "ltp":          ltp,
            "order_result": order_result,
            "reason":       reason,
            "exit_events":  exit_events,
            "portfolio":    get_portfolio_summary(),
        }


if __name__ == "__main__":
    import json
    trader = SectorTrader()
    result = trader.execute_daily_routine()
    print(json.dumps(result, indent=2, default=str))
