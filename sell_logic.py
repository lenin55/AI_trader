"""
Sell Logic Module for rupee50k-ai-sector-trader.
Evaluates all open positions daily and determines if any should be exited.

Exit conditions (applied in priority order):
  1. STOP_LOSS     — Current price dropped >= 5% below entry price (hard floor, non-negotiable)
  2. PROFIT_TARGET — Current price rose >= 15% above entry price (lock in gains)
  3. AI_EXIT       — Claude re-evaluates the original thesis vs today's news and recommends SELL

All exits are logged to PostgreSQL and trigger a real/paper SELL order via KiteClient.
"""

from datetime import date
from typing import List, Dict, Any

from config import logger
from database import (
    get_open_trades,
    close_trade,
    insert_evaluation,
)
from ai_decision import AIDecisionMaker

# ==========================================
# RISK / REWARD THRESHOLDS
# ==========================================
STOP_LOSS_PCT    = 0.05   # Exit immediately if price drops 5% from entry
PROFIT_TARGET_PCT = 0.15  # Exit and lock gains if price rises 15% from entry


class SellEngine:
    """
    Evaluates all open positions each trading day and exits when appropriate.
    Designed to be called from trading_logic.py after the BUY decision step.
    """

    def __init__(self, kite_client, ai_maker: AIDecisionMaker):
        """
        Args:
            kite_client: An initialised KiteClient instance (real or simulated).
            ai_maker:    An initialised AIDecisionMaker instance.
        """
        self.kite = kite_client
        self.ai   = ai_maker

    def run_daily_exit_checks(self, news_text: str) -> List[Dict[str, Any]]:
        """
        Main entry point. Iterates every open trade and applies exit rules.

        Args:
            news_text: Today's news string (already fetched by NewsFetcher).

        Returns:
            List of exit events, each a dict describing what happened.
        """
        open_trades = get_open_trades()

        if not open_trades:
            logger.info("No open positions to evaluate today.")
            return []

        logger.info(f"Evaluating {len(open_trades)} open position(s) for potential exits...")
        exit_events = []

        for trade in open_trades:
            event = self._evaluate_trade(trade, news_text)
            if event:
                exit_events.append(event)

        return exit_events

    # ------------------------------------------------------------------
    # PRIVATE: evaluate a single trade
    # ------------------------------------------------------------------

    def _evaluate_trade(self, trade: Dict[str, Any], news_text: str) -> Dict[str, Any]:
        """
        Applies all exit checks to one trade in priority order:
          1. Stop-loss (hard rule — checked before AI to save API calls)
          2. Profit target (hard rule)
          3. AI thesis re-evaluation (soft rule)
        """
        trade_id    = trade["id"]
        stock       = trade["stock"]
        sector      = trade["sector"] or "Unknown"
        entry_price = float(trade["entry_price"])
        quantity    = int(trade["quantity"])
        entry_date  = str(trade["entry_date"])
        entry_thesis = trade["entry_thesis"] or "No thesis recorded."

        # Fetch live price
        current_price = self.kite.get_ltp(stock)
        if current_price <= 0:
            logger.warning(f"[SellEngine] Could not fetch LTP for {stock}. Skipping exit check.")
            return {}

        pnl_per_share = current_price - entry_price
        pnl_total     = pnl_per_share * quantity
        pnl_pct       = (pnl_per_share / entry_price) * 100

        logger.info(
            f"[SellEngine] {stock} | Entry: ₹{entry_price} | "
            f"Current: ₹{current_price} | P&L: ₹{pnl_total:.2f} ({pnl_pct:.2f}%)"
        )

        # ---- Rule 1: Hard Stop-Loss ----
        if pnl_pct <= -(STOP_LOSS_PCT * 100):
            reason = (
                f"Stop-loss triggered at {pnl_pct:.2f}% loss "
                f"(threshold: -{STOP_LOSS_PCT*100:.0f}%). "
                f"Entry ₹{entry_price} → Current ₹{current_price}."
            )
            logger.warning(f"[SellEngine] STOP_LOSS triggered for {stock}. {reason}")
            return self._execute_exit(
                trade_id, stock, quantity, current_price,
                pnl_total, pnl_pct, "STOP_LOSS", reason,
                ai_verdict="SELL", thesis_intact=False
            )

        # ---- Rule 2: Profit Target ----
        if pnl_pct >= (PROFIT_TARGET_PCT * 100):
            reason = (
                f"Profit target reached at {pnl_pct:.2f}% gain "
                f"(threshold: +{PROFIT_TARGET_PCT*100:.0f}%). "
                f"Entry ₹{entry_price} → Current ₹{current_price}. Locking in gains."
            )
            logger.info(f"[SellEngine] PROFIT_TARGET hit for {stock}. {reason}")
            return self._execute_exit(
                trade_id, stock, quantity, current_price,
                pnl_total, pnl_pct, "PROFIT_TARGET", reason,
                ai_verdict="SELL", thesis_intact=True  # Good exit, thesis may still be intact
            )

        # ---- Rule 3: AI Thesis Re-Evaluation ----
        ai_eval = self.ai.evaluate_position(
            stock=stock,
            sector=sector,
            entry_price=entry_price,
            current_price=current_price,
            entry_date=entry_date,
            entry_thesis=entry_thesis,
            news_text=news_text
        )

        verdict       = ai_eval.get("verdict", "HOLD")
        thesis_intact = ai_eval.get("thesis_intact", True)
        reasoning     = ai_eval.get("reasoning", "No reasoning provided.")

        # Always persist the evaluation record (HOLD or SELL)
        insert_evaluation(
            trade_id=trade_id,
            eval_date=date.today(),
            current_price=current_price,
            current_pnl=pnl_total,
            pnl_pct=round(pnl_pct, 4),
            ai_verdict=verdict,
            ai_reasoning=reasoning,
            thesis_intact=thesis_intact
        )

        if verdict == "SELL":
            reason = f"AI recommended exit: thesis_intact={thesis_intact}. Reasoning: {reasoning}"
            logger.info(f"[SellEngine] AI_EXIT triggered for {stock}.")
            return self._execute_exit(
                trade_id, stock, quantity, current_price,
                pnl_total, pnl_pct, "AI_EXIT", reason,
                ai_verdict="SELL", thesis_intact=thesis_intact
            )

        # ---- No exit triggered — HOLD ----
        logger.info(f"[SellEngine] {stock} — HOLD. AI thesis intact: {thesis_intact}.")
        return {}

    # ------------------------------------------------------------------
    # PRIVATE: execute a SELL order and close the DB record
    # ------------------------------------------------------------------

    def _execute_exit(
        self,
        trade_id: int,
        stock: str,
        quantity: int,
        current_price: float,
        pnl_total: float,
        pnl_pct: float,
        exit_reason: str,
        reason_detail: str,
        ai_verdict: str,
        thesis_intact: bool
    ) -> Dict[str, Any]:
        """
        Places a SELL order via KiteClient and closes the trade in the database.
        """
        sell_result = self.kite.place_sell_order(stock, quantity)

        # Close trade in DB regardless of order status (prevents re-trying)
        close_trade(
            trade_id=trade_id,
            exit_price=current_price,
            exit_date=date.today(),
            exit_reason=exit_reason,
            pnl=round(pnl_total, 2)
        )

        # Also log the final evaluation row
        insert_evaluation(
            trade_id=trade_id,
            eval_date=date.today(),
            current_price=current_price,
            current_pnl=pnl_total,
            pnl_pct=round(pnl_pct, 4),
            ai_verdict=ai_verdict,
            ai_reasoning=reason_detail,
            thesis_intact=thesis_intact
        )

        logger.info(
            f"[SellEngine] Trade #{trade_id} ({stock} x{quantity}) CLOSED. "
            f"Reason: {exit_reason} | P&L: ₹{pnl_total:.2f} ({pnl_pct:.2f}%)"
        )

        return {
            "trade_id":    trade_id,
            "stock":       stock,
            "quantity":    quantity,
            "exit_price":  current_price,
            "exit_reason": exit_reason,
            "pnl":         round(pnl_total, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "sell_order":  sell_result,
            "reasoning":   reason_detail,
        }
