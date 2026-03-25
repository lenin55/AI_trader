"""
AI Decision Module for rupee50k-ai-sector-trader.
Uses an LLM via LangChain (Grok preferred, fallback to OpenAI/Gemini) to analyze
financial news and decide whether to BUY a liquid stock or stay NO_TRADE.
"""

import json
from enum import Enum
from typing import Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from config import XAI_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, LIQUID_UNIVERSE, logger

def get_llm():
    """Dynamically loads and returns the best available LLM provider."""
    if XAI_API_KEY and XAI_API_KEY != "your_xai_api_key_here":
        try:
            from langchain_xai import ChatXAI
            # Use grok-beta or specific model name provided by xai via langchain
            return ChatXAI(xai_api_key=XAI_API_KEY, model="grok-beta", temperature=0.1)
        except ImportError:
            logger.warning("langchain-xai is not installed, falling back.")

    if OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(openai_api_key=OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.1)
        except ImportError:
            logger.warning("langchain-openai is not installed, falling back.")
            
    if GOOGLE_API_KEY and GOOGLE_API_KEY != "your_gemini_api_key_here":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(google_api_key=GOOGLE_API_KEY, model="gemini-2.5-flash", temperature=0.1)
        except ImportError:
            logger.warning("langchain-google-genai is not installed.")
            
    raise ValueError("No valid LLM API key or LangChain provider package found. Please set XAI_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.")

class TradingAction(str, Enum):
    BUY = "BUY"
    NO_TRADE = "NO_TRADE"

class DecisionOutput(BaseModel):
    reason: str = Field(description="Step-by-step reasoning based strictly on the provided news.")
    sector: str = Field(description="The strongest sector chosen, or 'None' if NO_TRADE.")
    stock: str = Field(description="The chosen stock symbol from the Liquid Universe, or 'None' if NO_TRADE.")
    action: TradingAction = Field(description="Action to take: BUY or NO_TRADE.")

# The strict, conservative system prompt guaranteeing safety.
SYSTEM_PROMPT = """You are a highly conservative quantitative trading AI specializing in the Indian Stock Market (NSE).
Your task is to read the latest financial news and determine if there is a CLEAR, OVERWHELMING bullish edge for a specific sector today.

Capital preservation is your #1 priority. If the news is mixed, uncertain, lacks a strong positive catalyst for any sector, or mentions global economic fears, your action MUST be NO_TRADE.

Here is the Liquid Universe of stocks you are allowed to trade:
{liquid_universe}

Instructions:
1. Analyze the provided news for macroeconomic and sector-specific catalysts.
2. If there is a highly positive catalyst for a specific sector, identify that sector.
3. If a sector is chosen, select exactly ONE stock from the Liquid Universe that best represents or benefits from that sector.
4. If no sector has a clear bullish catalyst, or if the overall market sentiment is anxious/uncertain, set action to NO_TRADE, sector to None, and stock to None.
5. Provide a step-by-step reasoning justifying your choice or your reason for NO_TRADE.
6. Return the result strictly in the requested JSON format matching the schema.

News Data:
{news_data}
"""

class AIDecisionMaker:
    """Class to process news and generate a trading decision using LangChain."""
    
    def __init__(self):
        try:
            self.llm = get_llm()
            self.parser = JsonOutputParser(pydantic_object=DecisionOutput)
            self.prompt = PromptTemplate(
                template="System: {system}\n\nUser: Respond with the JSON structure.\n{format_instructions}",
                input_variables=["system"],
                partial_variables={"format_instructions": self.parser.get_format_instructions()}
            )
            self.chain = self.prompt | self.llm | self.parser
        except ValueError as e:
            logger.critical(str(e))
            self.llm = None
        
    def get_decision(self, news_text: str) -> Dict[str, Any]:
        """
        Processes news text through the LLM to get a trading decision.
        Returns a dict: {"action": "NO_TRADE", "sector": "None", "stock": "None", "reason": "..."}
        """
        if not self.llm:
            return {
                "action": "NO_TRADE",
                "sector": "None", 
                "stock": "None",
                "reason": "System error: LLM not initialized. Defaulting to NO_TRADE."
            }
            
        if not news_text or "Error" in news_text or "No recent" in news_text:
            logger.warning("Invalid or empty news text provided for decision. Defaulting to NO_TRADE.")
            return {
                "action": "NO_TRADE",
                "sector": "None", 
                "stock": "None",
                "reason": "Missing or error in news data. Capital preservation trigger."
            }
            
        logger.info("Sending news to LLM for sector analysis...")
        formatted_system_prompt = SYSTEM_PROMPT.format(
            liquid_universe=", ".join(LIQUID_UNIVERSE),
            news_data=news_text
        )
        
        try:
            result = self.chain.invoke({"system": formatted_system_prompt})
            
            action = result.get("action", "NO_TRADE")
            stock = result.get("stock", "None")
            
            # Hard Safety Check: Ignore BUY if the stock is hallucinated or unsupported
            if action == "BUY" and stock not in LIQUID_UNIVERSE:
                logger.warning(f"CRITICAL: LLM suggested BUY for {stock}, which is NOT in LIQUID_UNIVERSE! Overriding to NO_TRADE.")
                result["action"] = "NO_TRADE"
                result["reason"] = f"Original reason: {result.get('reason')}. OVERRIDE: Invalid stock hallucinated."
                
            logger.info(f"LLM Decision: {result.get('action')} | Stock: {result.get('stock')}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM decision: {e}")
            return {
                "action": "NO_TRADE",
                "sector": "None", 
                "stock": "None",
                "reason": f"LLM execution/parsing error: {e}"
            }

if __name__ == "__main__":
    # Test execution locally (Requires at least one valid API key in .env)
    dummy_news = "Article 1:\nTitle: IT Sector expects heavy inflow of US projects following recent deals.\nSummary: TCS and Infosys are well positioned for massive growth next quarter."
    decision_maker = AIDecisionMaker()
    print("=== DUMMY DECISION ===")
    print(json.dumps(decision_maker.get_decision(dummy_news), indent=2))
