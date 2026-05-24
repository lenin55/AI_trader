"""
Database module for NiftyMind.
Handles PostgreSQL persistence for trades, news logs, and daily evaluations.
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/trader_db")


def get_connection():
    """Returns a new psycopg2 connection."""
    return psycopg2.connect(DATABASE_URL)


def initialize_database():
    """
    Creates all required tables if they don't exist.
    Call once on startup (idempotent).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # --- Trades Table ---
            # Stores every BUY entry. Sell info is updated in-place.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id              SERIAL PRIMARY KEY,
                    stock           VARCHAR(20)     NOT NULL,
                    sector          VARCHAR(50),
                    quantity        INTEGER         NOT NULL,
                    entry_price     NUMERIC(12, 2)  NOT NULL,
                    entry_date      DATE            NOT NULL,
                    entry_thesis    TEXT,           -- The AI reasoning that triggered the BUY

                    -- Sell fields (NULL until position is closed)
                    exit_price      NUMERIC(12, 2),
                    exit_date       DATE,
                    exit_reason     VARCHAR(50),    -- 'STOP_LOSS', 'PROFIT_TARGET', 'AI_EXIT', 'MANUAL'
                    pnl             NUMERIC(12, 2), -- Realised P&L in ₹

                    status          VARCHAR(10) NOT NULL DEFAULT 'OPEN',  -- 'OPEN' or 'CLOSED'
                    order_id        VARCHAR(64),    -- Kite order ID (or simulated_ prefix)
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                );
            """)

            # --- Daily News Log ---
            # Stores every day's raw news snapshot for audit and re-analysis.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_news_log (
                    id              SERIAL PRIMARY KEY,
                    log_date        DATE            NOT NULL UNIQUE,
                    news_text       TEXT            NOT NULL,
                    article_count   INTEGER,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                );
            """)

            # --- Trade Evaluations ---
            # One row per open trade per day — the AI's hold/sell verdict.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_evaluations (
                    id              SERIAL PRIMARY KEY,
                    trade_id        INTEGER         NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
                    eval_date       DATE            NOT NULL,
                    current_price   NUMERIC(12, 2)  NOT NULL,
                    current_pnl     NUMERIC(12, 2)  NOT NULL,
                    pnl_pct         NUMERIC(8, 4)   NOT NULL,
                    ai_verdict      VARCHAR(10)     NOT NULL,  -- 'HOLD' or 'SELL'
                    ai_reasoning    TEXT,
                    thesis_intact   BOOLEAN,        -- Did AI consider original thesis still valid?
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
                    UNIQUE(trade_id, eval_date)
                );
            """)

            # --- Daily Decisions ---
            # Logs the macro AI decision (BUY/NO_TRADE) for the entire trading day.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_decisions (
                    id              SERIAL PRIMARY KEY,
                    decision_date   DATE            NOT NULL UNIQUE,
                    action          VARCHAR(20)     NOT NULL,
                    reason          TEXT,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                );
            """)

            # --- Trailing stop: add highest_price column if it doesn't exist yet ---
            cur.execute("""
                ALTER TABLE trades
                ADD COLUMN IF NOT EXISTS highest_price NUMERIC(12, 2);
            """)

            # --- Daily Equity Log ---
            # Tracks historical portfolio equity for charting
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_equity_log (
                    id              SERIAL PRIMARY KEY,
                    log_date        DATE            NOT NULL UNIQUE,
                    equity          NUMERIC(12, 2)  NOT NULL,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                );
            """)

        conn.commit()
        print("[DB] Database initialized successfully.")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"[DB] Failed to initialize database: {e}")
    finally:
        conn.close()


# ==========================================
# TRADE OPERATIONS
# ==========================================

def insert_trade(
    stock: str,
    sector: str,
    quantity: int,
    entry_price: float,
    entry_date: date,
    entry_thesis: str,
    order_id: str
) -> int:
    """Inserts a new BUY trade. Returns the new trade ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (stock, sector, quantity, entry_price, entry_date, entry_thesis, order_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN')
                RETURNING id;
            """, (stock, sector, quantity, entry_price, entry_date, entry_thesis, order_id))
            trade_id = cur.fetchone()[0]
        conn.commit()
        return trade_id
    finally:
        conn.close()


def close_trade(
    trade_id: int,
    exit_price: float,
    exit_date: date,
    exit_reason: str,
    pnl: float
):
    """Marks a trade as CLOSED with exit details."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trades
                SET exit_price = %s,
                    exit_date  = %s,
                    exit_reason = %s,
                    pnl        = %s,
                    status     = 'CLOSED'
                WHERE id = %s;
            """, (exit_price, exit_date, exit_reason, pnl, trade_id))
        conn.commit()
    finally:
        conn.close()


def get_open_trades() -> List[Dict[str, Any]]:
    """Returns all currently open (un-exited) trades as a list of dicts."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_date ASC;
            """)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_trade_by_id(trade_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single trade by its ID."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE id = %s;", (trade_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def already_holds_stock(stock: str) -> bool:
    """Returns True if there is already an open position in the given stock."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM trades WHERE stock = %s AND status = 'OPEN';",
                (stock,)
            )
            count = cur.fetchone()[0]
            return count > 0
    finally:
        conn.close()


def get_today_realised_pnl(for_date: date) -> float:
    """Returns the total realised P&L for trades closed today (for circuit breaker)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status = 'CLOSED' AND exit_date = %s;",
                (for_date,)
            )
            return float(cur.fetchone()[0])
    finally:
        conn.close()


def update_highest_price(trade_id: int, price: float):
    """Updates the highest_price seen for a trade (used for trailing stop-loss)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trades
                SET highest_price = GREATEST(COALESCE(highest_price, entry_price), %s)
                WHERE id = %s AND status = 'OPEN';
            """, (price, trade_id))
        conn.commit()
    finally:
        conn.close()


# ==========================================
# NEWS & MACRO DECISION OPERATIONS
# ==========================================

def log_daily_news(log_date: date, news_text: str, article_count: int):
    """Persists today's news snapshot. Upserts if already exists."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_news_log (log_date, news_text, article_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (log_date) DO UPDATE
                    SET news_text = EXCLUDED.news_text,
                        article_count = EXCLUDED.article_count;
            """, (log_date, news_text, article_count))
        conn.commit()
    finally:
        conn.close()


def get_news_for_date(log_date: date) -> Optional[str]:
    """Retrieves the stored news text for a given date."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT news_text FROM daily_news_log WHERE log_date = %s;",
                (log_date,)
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def log_daily_decision(decision_date: date, action: str, reason: str):
    """Persists the bot's overall daily macro decision (e.g. BUY, NO_TRADE)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_decisions (decision_date, action, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (decision_date) DO UPDATE
                    SET action = EXCLUDED.action,
                        reason = EXCLUDED.reason;
            """, (decision_date, action, reason))
        conn.commit()
    finally:
        conn.close()


def get_today_decision(decision_date: date) -> Optional[Dict[str, Any]]:
    """Retrieves the macro decision for a given date."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM daily_decisions WHERE decision_date = %s;",
                (decision_date,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


# ==========================================
# EVALUATION OPERATIONS
# ==========================================

def insert_evaluation(
    trade_id: int,
    eval_date: date,
    current_price: float,
    current_pnl: float,
    pnl_pct: float,
    ai_verdict: str,
    ai_reasoning: str,
    thesis_intact: bool
):
    """Saves a daily AI evaluation for an open trade."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trade_evaluations
                    (trade_id, eval_date, current_price, current_pnl, pnl_pct, ai_verdict, ai_reasoning, thesis_intact)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id, eval_date) DO UPDATE
                    SET ai_verdict   = EXCLUDED.ai_verdict,
                        ai_reasoning = EXCLUDED.ai_reasoning,
                        current_price = EXCLUDED.current_price,
                        current_pnl  = EXCLUDED.current_pnl,
                        pnl_pct      = EXCLUDED.pnl_pct,
                        thesis_intact = EXCLUDED.thesis_intact;
            """, (trade_id, eval_date, current_price, current_pnl, pnl_pct,
                  ai_verdict, ai_reasoning, thesis_intact))
        conn.commit()
    finally:
        conn.close()


def get_trade_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns closed trades, most recent first, for dashboard display."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM trades ORDER BY entry_date DESC LIMIT %s;
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_portfolio_summary() -> Dict[str, Any]:
    """Returns aggregated portfolio stats for the dashboard."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'OPEN')   AS open_positions,
                    COUNT(*) FILTER (WHERE status = 'CLOSED') AS closed_trades,
                    COALESCE(SUM(pnl) FILTER (WHERE status = 'CLOSED'), 0) AS total_realised_pnl,
                    COALESCE(SUM(pnl) FILTER (WHERE status = 'CLOSED' AND pnl > 0), 0) AS total_profit,
                    COALESCE(SUM(pnl) FILTER (WHERE status = 'CLOSED' AND pnl < 0), 0) AS total_loss,
                    COUNT(*) FILTER (WHERE status = 'CLOSED' AND pnl > 0) AS winning_trades,
                    COUNT(*) FILTER (WHERE status = 'CLOSED' AND pnl < 0) AS losing_trades
                FROM trades;
            """)
            return dict(cur.fetchone())
    finally:
        conn.close()


# ==========================================
# EQUITY LOGGING
# ==========================================

def log_daily_equity(log_date: date, equity: float):
    """Persists total portfolio equity for charting."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_equity_log (log_date, equity)
                VALUES (%s, %s)
                ON CONFLICT (log_date) DO UPDATE
                    SET equity = EXCLUDED.equity;
            """, (log_date, equity))
        conn.commit()
    finally:
        conn.close()


def get_equity_history(limit: int = 60) -> List[Dict[str, Any]]:
    """Returns daily equity history."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM daily_equity_log ORDER BY log_date ASC LIMIT %s;
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()



if __name__ == "__main__":
    initialize_database()
    print("Portfolio Summary:", get_portfolio_summary())
