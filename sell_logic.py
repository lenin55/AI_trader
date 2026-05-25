"""
Sell Logic Module for NiftyNinety.
Evaluates all open positions daily and determines if any should be exited.

Exit conditions (applied in priority order):
  1. TRAILING_STOP — Price falls >= 3% from the highest price seen since entry
  2. STOP_LOSS     — Current price dropped >= 5% below entry price (hard floor, non-negotiable)
  3. PROFIT_TARGET — Current price rose >= 15% above entry price (lock in gains)
  4. AI_EXIT       — Gemini re-evaluates the original thesis vs today's news and recommends SELL

All exits are logged to PostgreSQL and trigger a real/paper SELL order via KiteClient.
"""

from datetime import date
from typing import List, Dict, Any, Optional

from config import (
    logger,
    STOP_LOSS_PCT,
    PROFIT_TARGET_PCT,
    TRAILING_STOP_PCT,
    UserConfig
)
from database import (
    get_open_trades,
    close_trade,
    insert_evaluation,
    update_highest_price,
)
from ai_decision import AIDecisionMaker

try:
    from technical_analysis import get_technical_snapshot
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False


class SellEngine:
    """
    Evaluates all open positions each trading day and exits when appropriate.
    Designed to be called from trading_logic.py after the BUY decision step.
    """

    def __init__(self, kite_client, ai_maker: AIDecisionMaker, user_config: UserConfig):
        """
        Args:
            kite_client: An initialised KiteClient instance (real or simulated).
            ai_maker:    An initialised AIDecisionMaker instance.
            user_config: An initialised UserConfig instance.
        """
        self.kite = kite_client
        self.ai   = ai_maker
        self.user_config = user_config

    def run_daily_exit_checks(self, news_text: str) -> List[Dict[str, Any]]:
        """
        Main entry point. Iterates every open trade and applies exit rules.

        Args:
            news_text: Today's news string (already fetched by NewsFetcher).

        Returns:
            List of exit events, each a dict describing what happened.
        """
        open_trades = get_open_trades(self.user_config.user_id)

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
          1. Trailing stop-loss (adapts as price rises — lets winners run)
          2. Hard stop-loss from entry (absolute floor)
          3. Profit target (hard lock-in)
          4. AI thesis re-evaluation (soft rule)
        """
        trade_id     = trade["id"]
        stock        = trade["stock"]
        sector       = trade["sector"] or "Unknown"
        entry_price  = float(trade["entry_price"])
        quantity     = int(trade["quantity"])
        entry_date   = str(trade["entry_date"])
        entry_thesis = trade["entry_thesis"] or "No thesis recorded."
        # highest_price may be NULL for old trades — default to entry_price
        highest_price = float(trade["highest_price"]) if trade.get("highest_price") else entry_price

        # Fetch live price
        current_price = self.kite.get_ltp(stock)
        if current_price <= 0:
            logger.warning(f"[SellEngine] Could not fetch LTP for {stock}. Skipping exit check.")
            return {}

        # Update highest price seen (for trailing stop tracking)
        if current_price > highest_price:
            highest_price = current_price
            update_highest_price(trade_id, current_price)

        pnl_per_share = current_price - entry_price
        pnl_total     = pnl_per_share * quantity
        pnl_pct       = (pnl_per_share / entry_price) * 100
        drop_from_high_pct = ((current_price - highest_price) / highest_price) * 100

        logger.info(
            f"[SellEngine] {stock} | Entry: ₹{entry_price} | "
            f"High: ₹{highest_price} | Current: ₹{current_price} | "
            f"P&L: ₹{pnl_total:.2f} ({pnl_pct:.2f}%) | Drop from high: {drop_from_high_pct:.2f}%"
        )

        # ---- Rule 1: Trailing Stop-Loss ----
        # Only activates once position is profitable (price above entry)
        if current_price > entry_price and drop_from_high_pct <= -(TRAILING_STOP_PCT * 100):
            reason = (
                f"Trailing stop triggered: price fell {abs(drop_from_high_pct):.2f}% "
                f"from high of ₹{highest_price} "
                f"(threshold: -{TRAILING_STOP_PCT*100:.0f}%). "
                f"Current: ₹{current_price}. Locking in gains."
            )
            logger.warning(f"[SellEngine] TRAILING_STOP triggered for {stock}. {reason}")
            return self._execute_exit(
                trade_id, stock, quantity, current_price,
                pnl_total, pnl_pct, "TRAILING_STOP", reason,
                ai_verdict="SELL", thesis_intact=True
            )

        # ---- Rule 2: Hard Stop-Loss from entry ----
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

        # ---- Rule 3: Profit Target ----
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
                ai_verdict="SELL", thesis_intact=True
            )

        # ---- Rule 4: AI Thesis Re-Evaluation ----
        # Enrich with live TA snapshot for the specific stock
        ta_snapshot = ""
        if _TA_AVAILABLE:
            ta_data = get_technical_snapshot(stock)
            if ta_data:
                ta_snapshot = ta_data.get("signal_summary", "")

        ai_eval = self.ai.evaluate_position(
            stock=stock,
            sector=sector,
            entry_price=entry_price,
            current_price=current_price,
            entry_date=entry_date,
            entry_thesis=entry_thesis,
            news_text=news_text,
            ta_snapshot=ta_snapshot,
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
