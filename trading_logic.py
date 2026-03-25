"""
Trading Logic Module for rupee50k-ai-sector-trader.
Orchestrates the daily routine: fetches news, gets AI decision, calculates risk, and executes safely.
"""

from typing import Dict, Any
from kite_client import KiteClient
from news_fetcher import NewsFetcher
from ai_decision import AIDecisionMaker
from config import MAX_RISK_PER_TRADE, TOTAL_CAPITAL, logger

# We assume a fixed conservative 5% Stop-loss distance for delivery trades to calculate sizing
ASSUMED_SL_PERCENT = 0.05

class SectorTrader:
    def __init__(self):
        self.kite = KiteClient()
        self.news_fetcher = NewsFetcher()
        self.ai = AIDecisionMaker()
        
    def execute_daily_routine(self) -> Dict[str, Any]:
        """
        Runs the daily trading logic securely.
        """
        logger.info("=== STARTING DAILY TRADING ROUTINE ===")
        
        # 1. Check Funds
        available_funds = self.kite.get_available_funds()
        if available_funds < 1000:
            logger.critical(f"Insufficient funds to trade. Available: ₹{available_funds}")
            return {"status": "error", "message": "Low funds."}
            
        # 2. Fetch News
        news_text = self.news_fetcher.get_latest_indian_business_news(max_articles=15)
        
        # 3. Get AI Decision
        decision = self.ai.get_decision(news_text)
        action = decision.get("action", "NO_TRADE")
        stock = decision.get("stock", "None")
        reason = decision.get("reason", "No reason provided.")
        sector = decision.get("sector", "None")
        
        logger.info(f"AI suggests {action} for {stock}. Reason: {reason}")
        
        if action != "BUY" or stock == "None" or stock == "NO_TRADE":
            logger.info("No trade taken today. Preserving capital.")
            return {"status": "success", "action": "NO_TRADE", "reason": reason}
            
        # 4. Calculate Sizing & Risk Based on Strict ₹250 Rule
        ltp = self.kite.get_ltp(stock)
        if ltp <= 0:
            logger.error(f"Could not fetch valid LTP for {stock}. Aborting trade.")
            return {"status": "error", "message": "Invalid LTP."}
            
        # Stop loss amount per share
        risk_per_share = ltp * ASSUMED_SL_PERCENT
        
        # How many shares can we buy while strictly keeping risk <= MAX_RISK_PER_TRADE?
        allowed_qty_by_risk = int(MAX_RISK_PER_TRADE // risk_per_share)
        
        # How many shares can we afford outright with available capital?
        max_capital_for_trade = min(available_funds, TOTAL_CAPITAL)
        allowed_qty_by_funds = int(max_capital_for_trade // ltp)
        
        final_qty = min(allowed_qty_by_risk, allowed_qty_by_funds)
        
        if final_qty <= 0:
            logger.warning(f"Calculated Qty is 0. LTP: ₹{ltp}, Risk/Share: ₹{risk_per_share:.2f}. Stock too expensive for current MAX_RISK limit.")
            return {"status": "error", "message": "Calculated quantity is 0."}
            
        logger.info(f"Sizing Calculated -> Qty: {final_qty} (LTP: ₹{ltp}, Max Risk Allowed: ₹{MAX_RISK_PER_TRADE:.2f})")
        logger.info(f"Total Trade Value: ₹{final_qty * ltp:.2f}")
        
        # 5. Execute Order Securely
        order_result = self.kite.place_buy_order(symbol=stock, quantity=final_qty)
        
        return {
            "status": "success",
            "action": "BUY",
            "stock": stock,
            "quantity": final_qty,
            "ltp": ltp,
            "order_result": order_result,
            "reason": reason,
            "sector": sector
        }

if __name__ == "__main__":
    trader = SectorTrader()
    result = trader.execute_daily_routine()
    print("Routine Result:", result)
