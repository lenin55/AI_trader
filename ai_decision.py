"""
AI Decision Module for rupee50k-ai-sector-trader.
Uses Google Gemini for:
  1. Daily BUY / NO_TRADE decision based on news.
  2. Daily HOLD / SELL evaluation of existing open positions.
"""

import json
import os
from enum import Enum
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from config import LIQUID_UNIVERSE, logger

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


def get_gemini_client():
    from langchain_google_genai import ChatGoogleGenerativeAI
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_google_api_key_here":
        raise ValueError(
            "GOOGLE_API_KEY is missing or not set in .env file. "
            "Get your key from Google AI Studio."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=GOOGLE_API_KEY
    )


# ==========================================
# PROMPT 1 — DAILY BUY / NO_TRADE DECISION
# ==========================================

BUY_DECISION_PROMPT = """You are a highly conservative quantitative trading AI specialising in the Indian Stock Market (NSE).
Your task is to read the latest financial news and determine if there is a CLEAR, OVERWHELMING bullish edge for a specific sector today.

Capital preservation is your #1 priority. If the news is mixed, uncertain, lacks a strong positive catalyst, or mentions global economic fears, your action MUST be NO_TRADE.

Liquid Universe (ONLY stocks you may recommend):
{liquid_universe}

Instructions:
1. Analyse each news article for macroeconomic and sector-specific catalysts.
2. If ONE sector has an exceptionally strong, unambiguous positive catalyst, identify it.
3. Select exactly ONE stock from the Liquid Universe that best benefits from that sector.
4. If no clear bullish edge exists, set action=NO_TRADE, sector=None, stock=None.
5. Provide step-by-step chain-of-thought reasoning.
6. Return ONLY valid JSON matching this exact schema — no markdown, no preamble:

{{
  "action": "BUY" | "NO_TRADE",
  "sector": "<sector name or None>",
  "stock": "<NSE symbol or None>",
  "reason": "<step-by-step reasoning>"
}}

Today's News:
{news_data}"""


# ==========================================
# PROMPT 2 — DAILY HOLD / SELL EVALUATION
# ==========================================

HOLD_SELL_PROMPT = """You are a conservative portfolio risk manager for an Indian stock trading bot.
You must evaluate whether to HOLD or SELL an existing open position based on today's news.

Your job is to determine if the original investment thesis still holds.
If the thesis has reversed, weakened significantly, or if new risks have emerged for this stock/sector, you should recommend SELL.
If the original thesis is intact and no major negative catalysts have emerged, recommend HOLD.

Open Position Details:
- Stock: {stock}
- Sector: {sector}
- Entry Price: ₹{entry_price}
- Current Price: ₹{current_price}
- Unrealised P&L: ₹{current_pnl} ({pnl_pct:.2f}%)
- Entry Date: {entry_date}
- Original Entry Thesis: {entry_thesis}

Today's News:
{news_data}

Return ONLY valid JSON matching this exact schema — no markdown, no preamble:

{{
  "verdict": "HOLD" | "SELL",
  "thesis_intact": true | false,
  "reasoning": "<step-by-step reasoning referencing today's news>"
}}"""


class AIDecisionMaker:
    """
    Handles two types of AI decisions:
      1. get_decision()     — should we BUY something today?
      2. evaluate_position() — should we HOLD or SELL an open trade?
    """

    def __init__(self):
        try:
            self.llm = get_gemini_client()
            logger.info("Gemini AI client initialised.")
        except ValueError as e:
            logger.critical(str(e))
            self.llm = None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """
        Low-level Gemini API call. Returns raw text or None on failure.
        """
        if not self.llm:
            return None
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Unexpected error calling Gemini: {e}")
            return None

    def _parse_json_response(self, raw: str, context: str) -> Optional[Dict]:
        """Safely parses a JSON string from AI's response."""
        if not raw:
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        # Sometimes it returns ```json ...
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
            
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {context}: {e}\nRaw response: {raw[:300]}")
            return None

    # ------------------------------------------------------------------
    # PUBLIC METHOD 1: Daily BUY / NO_TRADE
    # ------------------------------------------------------------------

    def get_decision(self, news_text: str) -> Dict[str, Any]:
        """
        Analyses today's news and returns a BUY or NO_TRADE decision.
        """
        no_trade = {
            "action": "NO_TRADE",
            "sector": "None",
            "stock": "None",
            "reason": ""
        }

        if not self.llm:
            no_trade["reason"] = "System error: Gemini client not initialised. Defaulting to NO_TRADE."
            return no_trade

        if not news_text or news_text.startswith("Error") or "No recent" in news_text:
            no_trade["reason"] = "Missing or errored news data. Capital preservation triggered."
            logger.warning(no_trade["reason"])
            return no_trade

        prompt = BUY_DECISION_PROMPT.format(
            liquid_universe=", ".join(LIQUID_UNIVERSE),
            news_data=news_text
        )

        logger.info("Sending news to Gemini for sector analysis...")
        raw = self._call_gemini(prompt)
        result = self._parse_json_response(raw, "BUY_DECISION")

        if not result:
            no_trade["reason"] = f"Failed to parse Gemini response. Raw: {str(raw)[:200]}"
            return no_trade

        action = result.get("action", "NO_TRADE")
        stock  = result.get("stock", "None")

        # Hard safety check: reject hallucinated stocks not in universe
        if action == "BUY" and stock not in LIQUID_UNIVERSE:
            logger.warning(
                f"Gemini suggested BUY for '{stock}' which is NOT in LIQUID_UNIVERSE. "
                f"Overriding to NO_TRADE."
            )
            result["action"] = "NO_TRADE"
            result["stock"]  = "None"
            result["sector"] = "None"
            result["reason"] = (
                f"OVERRIDE: '{stock}' is not in the approved Liquid Universe. "
                f"Original reasoning: {result.get('reason', '')}"
            )

        logger.info(f"Gemini Decision: {result.get('action')} | Stock: {result.get('stock')}")
        return result

    # ------------------------------------------------------------------
    # PUBLIC METHOD 2: Daily HOLD / SELL evaluation
    # ------------------------------------------------------------------

    def evaluate_position(
        self,
        stock: str,
        sector: str,
        entry_price: float,
        current_price: float,
        entry_date: str,
        entry_thesis: str,
        news_text: str
    ) -> Dict[str, Any]:
        """
        Evaluates an open position daily and recommends HOLD or SELL.
        """
        default_hold = {
            "verdict": "HOLD",
            "thesis_intact": True,
            "reasoning": "Could not evaluate — defaulting to HOLD."
        }

        if not self.llm:
            return default_hold

        current_pnl = (current_price - entry_price) * 1  # per share
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        prompt = HOLD_SELL_PROMPT.format(
            stock=stock,
            sector=sector,
            entry_price=entry_price,
            current_price=current_price,
            current_pnl=round(current_pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            entry_date=entry_date,
            entry_thesis=entry_thesis,
            news_data=news_text
        )

        logger.info(f"Evaluating open position {stock} with Gemini...")
        raw = self._call_gemini(prompt)
        result = self._parse_json_response(raw, f"HOLD_SELL_{stock}")

        if not result:
            logger.warning(f"Could not parse hold/sell response for {stock}. Defaulting to HOLD.")
            return default_hold

        logger.info(
            f"Position eval for {stock}: {result.get('verdict')} | "
            f"Thesis intact: {result.get('thesis_intact')}"
        )
        return result


if __name__ == "__main__":
    dummy_news = (
        "Article 1:\\nTitle: IT Sector expects heavy inflow of US projects following recent deals.\\n"
        "Summary: TCS and Infosys are well positioned for massive growth next quarter."
    )
    maker = AIDecisionMaker()

    print("=== BUY DECISION TEST ===")
    decision = maker.get_decision(dummy_news)
    print(json.dumps(decision, indent=2))
