"""
Main entry point and scheduler for rupee50k-ai-sector-trader.
Runs the daily trading routine at 9:00 AM IST on weekdays.
"""

import time
import schedule
import pytz
from datetime import datetime
import sys

from config import logger
from trading_logic import SectorTrader

def job():
    """The registered scheduled job."""
    # Ensure it's a weekday (Monday=0 to Friday=4)
    tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz)
    
    if now_ist.weekday() >= 5:
        logger.info("Today is the weekend. Market is closed. Skipping routine.")
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
