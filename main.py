"""
Main entry point and scheduler for rupee50k-ai-sector-trader.
Runs the daily trading routine at 9:00 AM IST on weekdays (excluding NSE holidays).
"""

import time
import schedule
import pytz
from datetime import datetime, date
import sys

from config import logger
from trading_logic import SectorTrader

# NSE market holidays — update this list annually.
# Source: NSE India official holiday calendar.
NSE_HOLIDAYS = {
    # 2025
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramzan Eid)
    date(2025, 4, 10),   # Shri Ram Navami
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti / Good Friday
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 2),   # Dussehra
    date(2025, 10, 20),  # Diwali Laxmi Pujan (Muhurat Trading may differ)
    date(2025, 10, 21),  # Diwali Balipratipada
    date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev Ji
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 3),    # Mahashivratri
    date(2026, 3, 20),   # Holi
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 11, 11),  # Diwali (approx — update when NSE confirms)
    date(2026, 12, 25),  # Christmas
}


def is_market_open(today: date) -> bool:
    """Returns True only if today is a weekday and not an NSE holiday."""
    if today.weekday() >= 5:
        return False
    if today in NSE_HOLIDAYS:
        return False
    return True


def job():
    """The registered scheduled job."""
    tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz)
    today = now_ist.date()

    if not is_market_open(today):
        logger.info(f"Market closed today ({today}). Skipping routine.")
        return

    logger.info("Executing Scheduled Job...")
    trader = SectorTrader()
    trader.execute_daily_routine()
    logger.info("Scheduled Job Completed.")

def run_scheduler():
    """Sets up and runs the blocking scheduler."""
    logger.info("Starting Daily Scheduler. Waiting for 9:00 AM (local time match)...")
    
    # Schedule the job every day at a specific time (adjusts to local machine time,
    # if deploy target is IST, it runs at 09:00 IST).
    schedule.every().day.at("09:00").do(job)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler manually stopped.")

if __name__ == "__main__":
    # If run with --now, execute immediately once for testing/manual triggering.
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("Running job immediately (--now flag detected).")
        job()
    else:
        run_scheduler()
