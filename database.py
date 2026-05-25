"""
Database module for NiftyNinety.
Handles PostgreSQL persistence for users, trades, news logs, and daily evaluations.
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
    return psycopg2.connect(DATABASE_URL)

def initialize_database():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # --- Users Table ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id                  SERIAL PRIMARY KEY,
                    name                VARCHAR(100) NOT NULL,
                    email               VARCHAR(150) NOT NULL UNIQUE,
                    password_hash       VARCHAR(255) NOT NULL,
                    kite_api_key        VARCHAR(255),
                    kite_api_secret     VARCHAR(255),
                    kite_request_token  VARCHAR(255),
                    news_api_key        VARCHAR(255),
                    google_api_key      VARCHAR(255),
                    telegram_bot_token  VARCHAR(255),
                    telegram_chat_id    VARCHAR(255),
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            # --- Trades Table ---
            # Added user_id
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER         REFERENCES users(id) ON DELETE CASCADE,
                    stock           VARCHAR(20)     NOT NULL,
                    sector          VARCHAR(50),
                    quantity        INTEGER         NOT NULL,
                    entry_price     NUMERIC(12, 2)  NOT NULL,
                    entry_date      DATE            NOT NULL,
                    entry_thesis    TEXT,
                    exit_price      NUMERIC(12, 2),
                    exit_date       DATE,
                    exit_reason     VARCHAR(50),
                    pnl             NUMERIC(12, 2),
                    status          VARCHAR(10) NOT NULL DEFAULT 'OPEN',
                    order_id        VARCHAR(64),
                    highest_price   NUMERIC(12, 2),
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                );
            """)
            
            # --- Check if user_id exists in trades (for existing DBs) ---
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='trades' AND column_name='user_id';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE trades ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;")

            # --- Daily News Log --- (Global, no user_id needed)
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_evaluations (
                    id              SERIAL PRIMARY KEY,
                    trade_id        INTEGER         NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
                    eval_date       DATE            NOT NULL,
                    current_price   NUMERIC(12, 2)  NOT NULL,
                    current_pnl     NUMERIC(12, 2)  NOT NULL,
                    pnl_pct         NUMERIC(8, 4)   NOT NULL,
                    ai_verdict      VARCHAR(10)     NOT NULL,
                    ai_reasoning    TEXT,
                    thesis_intact   BOOLEAN,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
                    UNIQUE(trade_id, eval_date)
                );
            """)

            # --- Daily Decisions ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_decisions (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER         REFERENCES users(id) ON DELETE CASCADE,
                    decision_date   DATE            NOT NULL,
                    action          VARCHAR(20)     NOT NULL,
                    reason          TEXT,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, decision_date)
                );
            """)
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='daily_decisions' AND column_name='user_id';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE daily_decisions ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;")
                cur.execute("ALTER TABLE daily_decisions DROP CONSTRAINT IF EXISTS daily_decisions_decision_date_key;")
                cur.execute("ALTER TABLE daily_decisions ADD CONSTRAINT daily_decisions_user_date_key UNIQUE(user_id, decision_date);")


            # --- Daily Equity Log ---
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_equity_log (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER         REFERENCES users(id) ON DELETE CASCADE,
                    log_date        DATE            NOT NULL,
                    equity          NUMERIC(12, 2)  NOT NULL,
                    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, log_date)
                );
            """)
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='daily_equity_log' AND column_name='user_id';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE daily_equity_log ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;")
                cur.execute("ALTER TABLE daily_equity_log DROP CONSTRAINT IF EXISTS daily_equity_log_log_date_key;")
                cur.execute("ALTER TABLE daily_equity_log ADD CONSTRAINT daily_equity_log_user_date_key UNIQUE(user_id, log_date);")

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"[DB] Failed to initialize database: {e}")
    finally:
        conn.close()

# ==========================================
# USER OPERATIONS
# ==========================================

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def create_user(name: str, email: str, password_hash: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (name, email, password_hash))
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        conn.close()

def update_user_api_keys(user_id: int, keys: Dict[str, str]):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET 
                    kite_api_key = %s,
                    kite_api_secret = %s,
                    kite_request_token = %s,
                    news_api_key = %s,
                    google_api_key = %s,
                    telegram_bot_token = %s,
                    telegram_chat_id = %s
                WHERE id = %s;
            """, (
                keys.get("kite_api_key"),
                keys.get("kite_api_secret"),
                keys.get("kite_request_token"),
                keys.get("news_api_key"),
                keys.get("google_api_key"),
                keys.get("telegram_bot_token"),
                keys.get("telegram_chat_id"),
                user_id
            ))
        conn.commit()
    finally:
        conn.close()

# ==========================================
# TRADE OPERATIONS
# ==========================================

def insert_trade(user_id: int, stock: str, sector: str, quantity: int, entry_price: float, entry_date: date, entry_thesis: str, order_id: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (user_id, stock, sector, quantity, entry_price, entry_date, entry_thesis, order_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'OPEN')
                RETURNING id;
            """, (user_id, stock, sector, quantity, entry_price, entry_date, entry_thesis, order_id))
            trade_id = cur.fetchone()[0]
        conn.commit()
        return trade_id
    finally:
        conn.close()

def close_trade(trade_id: int, exit_price: float, exit_date: date, exit_reason: str, pnl: float):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trades
                SET exit_price = %s, exit_date = %s, exit_reason = %s, pnl = %s, status = 'CLOSED'
                WHERE id = %s;
            """, (exit_price, exit_date, exit_reason, pnl, trade_id))
        conn.commit()
    finally:
        conn.close()

def get_open_trades(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE user_id = %s AND status = 'OPEN' ORDER BY entry_date ASC;", (user_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_trade_by_id(trade_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE id = %s;", (trade_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def already_holds_stock(user_id: int, stock: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM trades WHERE user_id = %s AND stock = %s AND status = 'OPEN';", (user_id, stock))
            return cur.fetchone()[0] > 0
    finally:
        conn.close()

def get_today_realised_pnl(user_id: int, for_date: date) -> float:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE user_id = %s AND status = 'CLOSED' AND exit_date = %s;", (user_id, for_date))
            return float(cur.fetchone()[0])
    finally:
        conn.close()

def update_highest_price(trade_id: int, price: float):
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


def log_daily_news(log_date: date, news_text: str, article_count: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_news_log (log_date, news_text, article_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (log_date) DO UPDATE
                    SET news_text = EXCLUDED.news_text, article_count = EXCLUDED.article_count;
            """, (log_date, news_text, article_count))
        conn.commit()
    finally:
        conn.close()

def get_news_for_date(log_date: date) -> Optional[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT news_text FROM daily_news_log WHERE log_date = %s;", (log_date,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()

def log_daily_decision(user_id: int, decision_date: date, action: str, reason: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_decisions (user_id, decision_date, action, reason)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, decision_date) DO UPDATE
                    SET action = EXCLUDED.action, reason = EXCLUDED.reason;
            """, (user_id, decision_date, action, reason))
        conn.commit()
    finally:
        conn.close()

def get_today_decision(user_id: int, decision_date: date) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM daily_decisions WHERE user_id = %s AND decision_date = %s;", (user_id, decision_date))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def insert_evaluation(trade_id: int, eval_date: date, current_price: float, current_pnl: float, pnl_pct: float, ai_verdict: str, ai_reasoning: str, thesis_intact: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trade_evaluations
                    (trade_id, eval_date, current_price, current_pnl, pnl_pct, ai_verdict, ai_reasoning, thesis_intact)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id, eval_date) DO UPDATE
                    SET ai_verdict = EXCLUDED.ai_verdict, ai_reasoning = EXCLUDED.ai_reasoning,
                        current_price = EXCLUDED.current_price, current_pnl = EXCLUDED.current_pnl,
                        pnl_pct = EXCLUDED.pnl_pct, thesis_intact = EXCLUDED.thesis_intact;
            """, (trade_id, eval_date, current_price, current_pnl, pnl_pct, ai_verdict, ai_reasoning, thesis_intact))
        conn.commit()
    finally:
        conn.close()

def get_trade_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trades WHERE user_id = %s ORDER BY entry_date DESC LIMIT %s;", (user_id, limit))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_portfolio_summary(user_id: int) -> Dict[str, Any]:
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
                FROM trades WHERE user_id = %s;
            """, (user_id,))
            return dict(cur.fetchone())
    finally:
        conn.close()

def log_daily_equity(user_id: int, log_date: date, equity: float):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_equity_log (user_id, log_date, equity)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, log_date) DO UPDATE
                    SET equity = EXCLUDED.equity;
            """, (user_id, log_date, equity))
        conn.commit()
    finally:
        conn.close()

def get_equity_history(user_id: int, limit: int = 60) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM daily_equity_log WHERE user_id = %s ORDER BY log_date ASC LIMIT %s;", (user_id, limit))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def assign_orphaned_records_to_user(user_id: int):
    """Assigns existing records without a user to the default user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE trades SET user_id = %s WHERE user_id IS NULL;", (user_id,))
            cur.execute("UPDATE daily_decisions SET user_id = %s WHERE user_id IS NULL;", (user_id,))
            cur.execute("UPDATE daily_equity_log SET user_id = %s WHERE user_id IS NULL;", (user_id,))
        conn.commit()
    finally:
        conn.close()
