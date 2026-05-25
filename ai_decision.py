"""
AI Decision Module for NiftyNinety.
Uses Google Gemini for:
  1. Daily BUY / NO_TRADE decision based on news.
  2. Daily HOLD / SELL evaluation of existing open positions.
"""

import json
import os
from enum import Enum
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from config import LIQUID_UNIVERSE, logger, UserConfig


def get_gemini_client(api_key: str):
    from langchain_google_genai import ChatGoogleGenerativeAI
    if not api_key or api_key == "your_google_api_key_here":
        raise ValueError(
            "GOOGLE_API_KEY is missing or not set in .env file. "
            "Get your key from Google AI Studio."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=api_key
    )


# ==========================================
# PROMPT 1 — DAILY BUY / NO_TRADE DECISION
# ==========================================

BUY_DECISION_PROMPT = """You are an active daily quantitative swing trading AI specialising in the Indian Stock Market (NSE).
Your task is to read the latest financial news and identify the best relative opportunities for a specific sector today, even if the market is mixed.

You should aim to find at least one trade every day. However, if the news indicates a massive market crash, severe global economic fear, or extremely negative catalysts, your action MUST be NO_TRADE.

ADDITIONAL RULE — Technical filters (guidelines for selection):
- Avoid stocks with RSI > 80 (extreme overbought).
- Avoid stocks trading drastically below their 50-day SMA.
- Try to pick stocks that show relative strength and positive momentum based on the technical snapshot.
- If all available stocks look terrible technically and fundamentally, set action=NO_TRADE, but otherwise, pick the best 1-3 candidates.

Liquid Universe (ONLY stocks you may recommend):
{liquid_universe}

Technical Indicators (current snapshot):
{ta_context}

News Sentiment Summary (pre-scored):
{sentiment_context}

Instructions:
1. Analyse each news article for macroeconomic and sector-specific catalysts.
2. Identify up to 3 sectors that have the strongest relative catalysts today.
3. Select up to 3 stocks from the Liquid Universe that best benefit from those sectors or show relative strength.
4. Apply the technical filters above to filter out extremely bad setups.
5. If the market is severely crashing or all candidates are fundamentally flawed, set action=NO_TRADE and recommendations=[].
6. Provide step-by-step chain-of-thought reasoning.
7. Return ONLY valid JSON matching this exact schema — no markdown, no preamble:

{{
  "action": "BUY" | "NO_TRADE",
  "reason": "<overall macroeconomic reasoning>",
  "recommendations": [
    {{
      "stock": "<NSE symbol>",
      "sector": "<sector name>",
      "reason": "<stock specific reasoning>"
    }}
  ]
}}

Today's News:
{news_data}"""


# ==========================================
# PROMPT 2 — DAILY HOLD / SELL EVALUATION
# ==========================================

HOLD_SELL_PROMPT = """You are an active swing trading portfolio manager for an Indian stock trading bot.
You must evaluate whether to HOLD or SELL an existing open position based on today's news and technical data.

Your job is to determine if the trade is still optimal to hold.
- If the original thesis has reversed, new risks have emerged, or technical momentum has completely stalled, you should recommend SELL.
- If the stock has made a decent profit but seems to be losing upward momentum (TA weakness), you can recommend SELL to lock in gains early.
- If the original thesis is intact, momentum is strong, and no negative catalysts have emerged, recommend HOLD.

Open Position Details:
- Stock: {stock}
- Sector: {sector}
- Entry Price: ₹{entry_price}
- Current Price: ₹{current_price}
- Unrealised P&L: ₹{current_pnl} ({pnl_pct:.2f}%)
- Entry Date: {entry_date}
- Original Entry Thesis: {entry_thesis}

Current Technical Snapshot:
{ta_snapshot}

Today's News:
{news_data}

Return ONLY valid JSON matching this exact schema — no markdown, no preamble:

{{
  "verdict": "HOLD" | "SELL",
  "thesis_intact": true | false,
  "reasoning": "<step-by-step reasoning referencing today's news and technical data>"
}}"""


class AIDecisionMaker:
    """
    Handles two types of AI decisions:
      1. get_decision()     — should we BUY something today?
      2. evaluate_position() — should we HOLD or SELL an open trade?
    """

    def __init__(self, user_config: UserConfig = None):
        self.user_config = user_config
        try:
            api_key = self.user_config.google_api_key if self.user_config else ""
            self.llm = get_gemini_client(api_key)
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

    def get_decision(
        self,
        news_text: str,
        ta_context: str = "",
        sentiment_context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyses today's news (plus optional TA and sentiment) and returns a BUY or NO_TRADE decision.

        Args:
            news_text: Formatted news string from NewsFetcher.
            ta_context: Multi-stock technical indicator summary from technical_analysis.py.
            sentiment_context: Sector sentiment scores from NewsFetcher.get_sector_sentiment().
        """
        no_trade = {
            "action": "NO_TRADE",
            "reason": "",
            "recommendations": []
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
            ta_context=ta_context or "Technical data unavailable — skip technical filters.",
            sentiment_context=sentiment_context or "Sentiment data unavailable.",
            news_data=news_text
        )

        logger.info("Sending news to Gemini for sector analysis...")
        raw = self._call_gemini(prompt)
        result = self._parse_json_response(raw, "BUY_DECISION")

        if not result:
            no_trade["reason"] = f"Failed to parse Gemini response. Raw: {str(raw)[:200]}"
            return no_trade

        action = result.get("action", "NO_TRADE")
        recs = result.get("recommendations", [])

        # Hard safety check: reject hallucinated stocks not in universe
        valid_recs = []
        for rec in recs:
            stock = rec.get("stock", "")
            if stock in LIQUID_UNIVERSE:
                valid_recs.append(rec)
            else:
                logger.warning(
                    f"Gemini suggested BUY for '{stock}' which is NOT in LIQUID_UNIVERSE. "
                    f"Skipping this recommendation."
                )
        
        result["recommendations"] = valid_recs
        
        if action == "BUY" and not valid_recs:
            result["action"] = "NO_TRADE"
            result["reason"] = (
                f"OVERRIDE: All recommended stocks were not in the approved Liquid Universe. "
                f"Original reasoning: {result.get('reason', '')}"
            )

        logger.info(f"Gemini Decision: {result.get('action')} | Stocks: {[r.get('stock') for r in result.get('recommendations', [])]}")
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
        news_text: str,
        ta_snapshot: str = ""
    ) -> Dict[str, Any]:
        """
        Evaluates an open position daily and recommends HOLD or SELL.

        Args:
            ta_snapshot: Single-stock TA summary string from technical_analysis.get_technical_snapshot().
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
            ta_snapshot=ta_snapshot or "Technical data unavailable.",
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
