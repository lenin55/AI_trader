"""
Configuration module for NiftyNinety.
Handles environment variables, logging setup, and strict risk parameters.
"""

import os
import logging
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# TRADING & RISK PARAMETERS
# ==========================================
# CRITICAL SAFETY: Never enable LIVE_MODE unless explicitly testing with real money.
# Default is safely False (Paper mode)
LIVE_MODE: bool = os.getenv("LIVE_MODE", "False").lower() in ("true", "1", "t", "yes")

# Capital allocation
TOTAL_CAPITAL: float = float(os.getenv("TOTAL_CAPITAL", "50000.0"))
MAX_RISK_PER_TRADE_PCT: float = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "0.005"))
MAX_RISK_PER_TRADE: float = TOTAL_CAPITAL * MAX_RISK_PER_TRADE_PCT  # STRICT risk per trade
MAX_SIMULATED_DAILY_LOSS: float = TOTAL_CAPITAL * 0.01  # Auto-pause threshold (1% overall drawdown)

# Trade Management Thresholds
STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.05"))
PROFIT_TARGET_PCT: float = float(os.getenv("PROFIT_TARGET_PCT", "0.08"))
TRAILING_STOP_PCT: float = float(os.getenv("TRAILING_STOP_PCT", "0.03"))

# Execution parameters
ORDER_PRODUCT: str = "CNC"  # Delivery only, NO intraday leverage (no MIS/BO/CO)
ORDER_TYPE: str = "MARKET"

# Universe of highly liquid NSE stocks (Nifty 50 focused) to find daily opportunities
LIQUID_UNIVERSE: List[str] = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "ITC", "TCS", "LT", 
    "BAJFINANCE", "BHARTIARTL", "SBIN", "HINDUNILVR", "KOTAKBANK", 
    "AXISBANK", "M&M", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "TITAN", 
    "NTPC", "TATAMOTORS", "TATASTEEL", "POWERGRID", "ASIANPAINT", 
    "HCLTECH", "BAJAJFINSV", "WIPRO", "ADANIENT", "ADANIPORTS", 
    "COALINDIA", "ONGC", "GRASIM", "TECHM", "HINDALCO", "JSWSTEEL", 
    "CIPLA", "APOLLOHOSP", "TATACONSUM", "DRREDDY", "BAJAJ-AUTO", 
    "BRITANNIA", "EICHERMOT", "DIVISLAB", "INDUSINDBK", "HEROMOTOCO", 
    "SHREECEM", "BPCL", "LTIM", "NESTLEIND", "DLF"
]

# API CREDENTIALS
# ==========================================
class UserConfig:
    def __init__(self, user_dict):
        self.user_id = user_dict.get('id')
        self.kite_api_key = user_dict.get('kite_api_key', '')
        self.kite_api_secret = user_dict.get('kite_api_secret', '')
        self.kite_request_token = user_dict.get('kite_request_token', '')
        self.news_api_key = user_dict.get('news_api_key', '')
        self.google_api_key = user_dict.get('google_api_key', '')
        self.telegram_bot_token = user_dict.get('telegram_bot_token', '')
        self.telegram_chat_id = user_dict.get('telegram_chat_id', '')
        
        # Keep these as environment variable fallbacks if needed
        self.xai_api_key = os.getenv("XAI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

# ==========================================
# LOGGING SETUP
# ==========================================
import colorlog

def setup_logger(name: str) -> logging.Logger:
    """Sets up a colored console and file logger."""
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Route all levels to handlers
    
    if not logger.handlers:
        # File Handler (logs to file)
        file_handler = logging.FileHandler(f"logs/trading_bot.log")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console Handler (Colorized output)
        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
    return logger

# Default logger instance for use across modules
logger = setup_logger("NiftyNinety")

if __name__ == "__main__":
    logger.info(f"Configuration loaded. LIVE_MODE = {LIVE_MODE}")
