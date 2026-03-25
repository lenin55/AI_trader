"""
Kite Client module for rupee50k-ai-sector-trader.
Provides a secure wrapper around Zerodha's Kite Connect API for market data and orders.
"""

from typing import Dict, Any, Optional
from kiteconnect import KiteConnect

from config import (
    KITE_API_KEY, KITE_API_SECRET, KITE_REQUEST_TOKEN,
    LIVE_MODE, ORDER_PRODUCT, ORDER_TYPE, logger
)

class KiteClient:
    """Wrapper for Zerodha Kite Connect API to abstract safely for the trading bot."""
    
    def __init__(self):
        """Initializes the KiteConnect instance and handles authentication."""
        self.kite: Optional[KiteConnect] = None
        self.access_token: Optional[str] = None
        self._initialize_client()

    def _initialize_client(self):
        """Sets up the client using provided keys."""
        if not KITE_API_KEY or KITE_API_KEY == "your_kite_api_key_here":
            logger.warning("KITE_API_KEY is not configured. KiteClient will run in SIMULATED OFFLINE mode.")
            return

        try:
            self.kite = KiteConnect(api_key=KITE_API_KEY)
            
            # Request token is generated manually via Kite login URL daily.
            if KITE_REQUEST_TOKEN and KITE_REQUEST_TOKEN != "your_daily_kite_request_token_here":
                data = self.kite.generate_session(KITE_REQUEST_TOKEN, api_secret=KITE_API_SECRET)
                self.access_token = data["access_token"]
                self.kite.set_access_token(self.access_token)
                logger.info("Successfully connected to Kite API and generated access token.")
            else:
                logger.warning("No valid KITE_REQUEST_TOKEN provided. Operating in limited/offline mode.")
        
        except Exception as e:
            logger.error(f"Failed to initialize Kite Client: {e}")
            self.kite = None
            
    def get_ltp(self, symbol: str) -> float:
        """
        Fetches the Latest Traded Price (LTP) for an NSE equity symbol.
        Returns 0.0 if failed, or a dummy price if running completely offline/simulated.
        """
        # For development or running the bot without daily api keys, gracefully degrade
        if not self.kite or not self.access_token:
            logger.warning(f"[SIMULATED API] Returning dummy LTP 1000.0 for {symbol}")
            return 1000.0
            
        instrument = f"NSE:{symbol}"
        try:
            quote = self.kite.ltp([instrument])
            price = quote.get(instrument, {}).get("last_price", 0.0)
            logger.info(f"Fetched realtime LTP for {symbol}: ₹{price}")
            return price
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            return 0.0

    def get_available_funds(self) -> float:
        """
        Retrieves the available cash margin for equity delivery trading.
        """
        if not self.kite or not self.access_token:
            logger.warning("[SIMULATED API] Returning dummy funds (₹50000.0)")
            return 50000.0
            
        try:
            margins = self.kite.margins("equity")
            available = margins.get("available", {}).get("live_balance", 0.0)
            logger.info(f"Available funds fetched: ₹{available}")
            return available
        except Exception as e:
            logger.error(f"Error fetching funds from Kite API: {e}")
            return 0.0

    def place_buy_order(self, symbol: str, quantity: int) -> Dict[str, Any]:
        """
        Places a BUY order for the specified quantity.
        If LIVE_MODE is False (Paper Tracking), it merely logs it to console and file, preventing real capital usage.
        """
        if quantity <= 0:
            logger.error(f"Cannot place order for {symbol} with quantity {quantity}. Must be > 0.")
            return {"status": "error", "message": "Invalid quantity."}
            
        logger.info(f"PREPARING {'LIVE' if LIVE_MODE else 'PAPER'} ORDER -> Action: BUY | Symbol: {symbol} | Qty: {quantity} | Type: {ORDER_TYPE} | Product: {ORDER_PRODUCT}")
        
        # === SAFETY GATE ===
        if not LIVE_MODE:
            logger.info(f"✅ PAPER TRADE PLACED: Bought {quantity} qty of {symbol}.")
            # Provide a dummy order ID for local simulation
            from datetime import datetime
            return {
                "status": "success", 
                "order_id": f"simulated_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
        if not self.kite:
            logger.error(f"Cannot place live order: Kite client not initialized correctly.")
            return {"status": "error", "message": "Client not authenticated. Missing Request Token."}
            
        try:
            # Send real order to exchange
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=self.kite.EXCHANGE_NSE,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                order_type=self.kite.ORDER_TYPE_MARKET if ORDER_TYPE == "MARKET" else self.kite.ORDER_TYPE_LIMIT,
                product=self.kite.PRODUCT_CNC if ORDER_PRODUCT == "CNC" else self.kite.PRODUCT_MIS,
                validity=self.kite.VALIDITY_DAY
            )
            logger.info(f"✅ REAL LIVE ORDER PLACED SUCCESSFULLY. Order ID: {order_id}")
            return {"status": "success", "order_id": order_id}
            
        except Exception as e:
            logger.critical(f"FAILED TO PLACE LIVE ORDER for {symbol}: {e}")
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Test execution locally safely (in paper mode)
    client = KiteClient()
    print(f"Testing LTP for RELIANCE: {client.get_ltp('RELIANCE')}")
    print(f"Testing Funds check: {client.get_available_funds()}")
    print("Testing Paper Order placement:")
    print(client.place_buy_order("INFY", 5))
