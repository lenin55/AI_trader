"""
Notifier module for NiftyNinety.
Sends real-time alerts to Telegram for all significant trading events.

Alert types:
  - BUY executed
  - SELL / exit triggered (with reason and P&L)
  - Daily summary (portfolio status, today's decision)
  - Circuit breaker / halt
  - Error / critical failure
"""

import requests
from typing import Optional
from config import LIVE_MODE, logger, UserConfig


def _send_telegram(message: str, user_config: UserConfig = None) -> bool:
    """
    Sends a message to the configured Telegram chat.
    Returns True on success, False on failure.
    Silently skips if credentials are not configured.
    """
    if not user_config or not user_config.telegram_bot_token or not user_config.telegram_chat_id:
        return False  # Telegram not configured — silent skip

    url = f"https://api.telegram.org/bot{user_config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": user_config.telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=8)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"[Notifier] Failed to send Telegram alert: {e}")
        return False


def _mode_tag() -> str:
    return "🔴 *LIVE*" if LIVE_MODE else "📋 *PAPER*"


def notify_buy(stock: str, sector: str, quantity: int, price: float, trade_id: int, reason: str, user_config: UserConfig = None):
    """Alert when a BUY order is placed."""
    msg = (
        f"{_mode_tag()} — *BUY EXECUTED* ✅\n"
        f"Stock: `{stock}` | Sector: {sector}\n"
        f"Qty: {quantity} @ ₹{price:.2f}\n"
        f"Trade value: ₹{quantity * price:.2f}\n"
        f"Trade ID: #{trade_id}\n"
        f"Reason: _{reason[:200]}_"
    )
    if user_config: _send_telegram(msg, user_config)
    logger.info(f"[Notifier] BUY alert sent for {stock}.")


def notify_sell(
    stock: str,
    quantity: int,
    exit_price: float,
    pnl: float,
    pnl_pct: float,
    exit_reason: str,
    trade_id: int,
    user_config: UserConfig = None
):
    """Alert when a position is closed."""
    pnl_emoji = "✅" if pnl >= 0 else "🔴"
    msg = (
        f"{_mode_tag()} — *POSITION CLOSED* {pnl_emoji}\n"
        f"Stock: `{stock}` | Qty: {quantity}\n"
        f"Exit @ ₹{exit_price:.2f}\n"
        f"P&L: ₹{pnl:+.2f} ({pnl_pct:+.2f}%)\n"
        f"Exit Reason: `{exit_reason}`\n"
        f"Trade ID: #{trade_id}"
    )
    if user_config: _send_telegram(msg, user_config)
    logger.info(f"[Notifier] SELL alert sent for {stock} (reason: {exit_reason}).")


def notify_circuit_breaker(today_pnl: float, limit: float, user_config: UserConfig = None):
    """Alert when the daily loss circuit breaker halts trading."""
    msg = (
        f"{_mode_tag()} — ⚠️ *CIRCUIT BREAKER TRIGGERED*\n"
        f"Today's realised loss: ₹{today_pnl:.2f}\n"
        f"Daily limit: ₹{limit:.2f}\n"
        f"No new trades will be placed today."
    )
    if user_config: _send_telegram(msg, user_config)
    logger.warning("[Notifier] Circuit breaker alert sent.")


def notify_no_trade(reason: str, user_config: UserConfig = None):
    """Alert for daily NO_TRADE decision (brief)."""
    msg = (
        f"{_mode_tag()} — *NO TRADE today* 💤\n"
        f"_{reason[:300]}_"
    )
    if user_config: _send_telegram(msg, user_config)


def notify_daily_summary(portfolio: dict, action: str, reason: str, user_config: UserConfig = None):
    """End-of-routine daily summary."""
    open_pos    = portfolio.get("open_positions", 0)
    closed      = portfolio.get("closed_trades", 0)
    total_pnl   = portfolio.get("total_realised_pnl", 0)
    wins        = portfolio.get("winning_trades", 0)
    losses      = portfolio.get("losing_trades", 0)
    win_rate    = round((wins / closed * 100) if closed > 0 else 0, 1)

    msg = (
        f"{_mode_tag()} — *Daily Summary* 📊\n"
        f"Today's Decision: `{action}`\n"
        f"Open Positions: {open_pos}\n"
        f"Closed Trades: {closed} (W:{wins} / L:{losses} | Win rate: {win_rate}%)\n"
        f"Total Realised P&L: ₹{total_pnl:+.2f}\n"
        f"Note: _{reason[:200]}_"
    )
    if user_config: _send_telegram(msg, user_config)
    logger.info("[Notifier] Daily summary sent.")


def notify_error(context: str, error: str, user_config: UserConfig = None):
    """Alert on critical errors."""
    msg = (
        f"{_mode_tag()} — 🚨 *ERROR*\n"
        f"Context: `{context}`\n"
        f"Error: `{error[:300]}`"
    )
    if user_config: _send_telegram(msg, user_config)
