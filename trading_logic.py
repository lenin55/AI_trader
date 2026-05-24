"""
Trading Logic Module for NiftyMind.
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
from notifier import (
    notify_buy,
    notify_sell,
    notify_circuit_breaker,
    notify_no_trade,
    notify_daily_summary,
    notify_error,
)
from database import (
    initialize_database,
    insert_trade,
    log_daily_news,
    log_daily_decision,
    already_holds_stock,
    get_portfolio_summary,
    get_today_realised_pnl,
)
from config import (
    MAX_RISK_PER_TRADE,
    TOTAL_CAPITAL,
    MAX_SIMULATED_DAILY_LOSS,
    STOP_LOSS_PCT,
    logger
)

try:
    from technical_analysis import get_ta_context_for_universe
    from config import LIQUID_UNIVERSE
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False


class NiftyMind:

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
            msg = f"Insufficient funds: ₹{available_funds}"
            logger.critical(msg)
            notify_error("funds_check", msg)
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

        # Compute sector sentiment for AI context
        sentiment_context = self.news_fetcher.get_sector_sentiment(news_text)
        logger.info("Sector sentiment computed.")

        # Compute technical indicators for the full universe
        ta_context = ""
        if _TA_AVAILABLE:
            logger.info("Fetching technical indicators for LIQUID_UNIVERSE...")
            ta_context = get_ta_context_for_universe(LIQUID_UNIVERSE)

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
                # Fire Telegram alert for each exit
                notify_sell(
                    stock=event.get("stock", "?"),
                    quantity=event.get("quantity", 0),
                    exit_price=event.get("exit_price", 0),
                    pnl=event.get("pnl", 0),
                    pnl_pct=event.get("pnl_pct", 0),
                    exit_reason=event.get("exit_reason", "UNKNOWN"),
                    trade_id=event.get("trade_id", 0),
                )

        # -------------------------------------------------------
        # 3. Daily loss circuit breaker
        # -------------------------------------------------------
        today_pnl = get_today_realised_pnl(today)
        if today_pnl <= -MAX_SIMULATED_DAILY_LOSS:
            logger.critical(
                f"Daily loss circuit breaker triggered! "
                f"Today's realised P&L: ₹{today_pnl:.2f} exceeds limit ₹{-MAX_SIMULATED_DAILY_LOSS:.2f}. "
                f"No new trades will be placed today."
            )
            notify_circuit_breaker(today_pnl, MAX_SIMULATED_DAILY_LOSS)
            log_daily_decision(decision_date=today, action="HALTED", reason=f"Circuit breaker: daily loss ₹{today_pnl:.2f}")
            portfolio = get_portfolio_summary()
            notify_daily_summary(portfolio, "HALTED", f"Circuit breaker triggered at ₹{today_pnl:.2f}")
            return {
                "status":      "halted",
                "action":      "NO_TRADE",
                "reason":      f"Circuit breaker: today's loss ₹{today_pnl:.2f} >= limit ₹{MAX_SIMULATED_DAILY_LOSS:.2f}.",
                "exit_events": exit_events,
                "portfolio":   portfolio,
            }

        # -------------------------------------------------------
        # 4. Get AI BUY decision for today (with TA + sentiment context)
        # -------------------------------------------------------
        decision = self.ai.get_decision(
            news_text=news_text,
            ta_context=ta_context,
            sentiment_context=sentiment_context,
        )
        action = decision.get("action", "NO_TRADE")
        reason = decision.get("reason", "No reason.")
        recs   = decision.get("recommendations", [])

        logger.info(f"AI suggests {action} with {len(recs)} recommendations.")

        # Persist the macro decision for the dashboard to display
        log_daily_decision(decision_date=today, action=action, reason=reason)

        if action != "BUY" or not recs:
            logger.info("No new trade taken today. Preserving capital.")
            notify_no_trade(reason)
            portfolio = get_portfolio_summary()
            notify_daily_summary(portfolio, action, reason)
            self._log_equity()
            return {
                "status":       "success",
                "action":       "NO_TRADE",
                "reason":       reason,
                "exit_events":  exit_events,
                "portfolio":    portfolio,
            }

        # -------------------------------------------------------
        # Loop through recommendations and place orders
        # -------------------------------------------------------
        placed_orders = []
        for rec in recs:
            stock = rec.get("stock")
            sector = rec.get("sector", "Unknown")
            rec_reason = rec.get("reason", "No reason provided.")
            
            if already_holds_stock(stock):
                logger.warning(
                    f"Already holding an open position in {stock}. "
                    f"Skipping new BUY to avoid overexposure."
                )
                continue

            ltp = self.kite.get_ltp(stock)
            if ltp <= 0:
                logger.error(f"Invalid LTP for {stock}. Skipping BUY.")
                notify_error("ltp_fetch", f"Invalid LTP for {stock}")
                continue

            risk_per_share       = ltp * STOP_LOSS_PCT
            allowed_qty_by_risk  = int(MAX_RISK_PER_TRADE // risk_per_share)
            max_capital_for_trade = min(available_funds, TOTAL_CAPITAL)
            allowed_qty_by_funds = int(max_capital_for_trade // ltp)
            final_qty            = min(allowed_qty_by_risk, allowed_qty_by_funds)

            if final_qty <= 0:
                logger.warning(f"Calculated qty is 0 for {stock} at ₹{ltp}. Skipping.")
                continue

            logger.info(
                f"Sizing: {final_qty} shares of {stock} @ ₹{ltp} "
                f"| Trade value: ₹{final_qty * ltp:.2f} "
                f"| Max risk: ₹{MAX_RISK_PER_TRADE:.2f}"
            )

            order_result = self.kite.place_buy_order(symbol=stock, quantity=final_qty)

            if order_result.get("status") != "success":
                msg = order_result.get("message", "Order failed.")
                logger.error(f"BUY order failed for {stock}: {msg}")
                notify_error("buy_order", msg)
                continue

            trade_id = insert_trade(
                stock=stock,
                sector=sector,
                quantity=final_qty,
                entry_price=ltp,
                entry_date=today,
                entry_thesis=rec_reason,
                order_id=order_result.get("order_id", "unknown"),
            )
            logger.info(f"Trade #{trade_id} persisted to DB: BUY {final_qty} x {stock} @ ₹{ltp}")

            notify_buy(
                stock=stock,
                sector=sector,
                quantity=final_qty,
                price=ltp,
                trade_id=trade_id,
                reason=rec_reason,
            )
            
            placed_orders.append({
                "trade_id": trade_id,
                "stock": stock,
                "quantity": final_qty,
                "price": ltp
            })
            
            # Deduct funds for next iteration
            available_funds -= (final_qty * ltp)

        portfolio = get_portfolio_summary()
        summary_msg = f"Bought {len(placed_orders)} stocks: " + ", ".join([o["stock"] for o in placed_orders]) if placed_orders else "No buys placed."
        notify_daily_summary(portfolio, "BUY" if placed_orders else "NO_TRADE", summary_msg)
        
        self._log_equity()

        return {
            "status":       "success",
            "action":       "BUY" if placed_orders else "NO_TRADE",
            "placed_orders": placed_orders,
            "reason":       reason,
            "exit_events":  exit_events,
            "portfolio":    portfolio,
        }

    def _log_equity(self):
        """Helper to calculate and log today's equity"""
        from database import get_open_trades, log_daily_equity, get_portfolio_summary
        from config import TOTAL_CAPITAL, LIVE_MODE
        
        open_trades = get_open_trades()
        summary = get_portfolio_summary()
        
        if not LIVE_MODE:
            unrealised_pnl = 0
            for t in open_trades:
                ltp = self.kite.get_ltp(t["stock"])
                if ltp > 0:
                    unrealised_pnl += (ltp - float(t["entry_price"])) * int(t["quantity"])
            total_realised_pnl = float(summary.get("total_realised_pnl", 0))
            equity = TOTAL_CAPITAL + total_realised_pnl + unrealised_pnl
        else:
            funds = self.kite.get_available_funds()
            open_val = 0
            for t in open_trades:
                ltp = self.kite.get_ltp(t["stock"])
                if ltp > 0:
                    open_val += int(t["quantity"]) * ltp
            equity = funds + open_val
            
        log_daily_equity(date.today(), equity)
        logger.info(f"Daily equity logged: ₹{equity:.2f}")


if __name__ == "__main__":
    import json
    trader = NiftyMind()
    result = trader.execute_daily_routine()
    print(json.dumps(result, indent=2, default=str))
