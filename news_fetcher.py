"""
News Fetcher module for NiftyNinety.
Retrieves the latest business and economic news for India using NewsData.io API.
Also provides lightweight sector sentiment scoring using VADER.
"""

import re
import requests
from typing import Dict, List
from config import logger

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False
    logger.warning("vaderSentiment not installed — sentiment scoring unavailable. Run: pip install vaderSentiment")

# Keyword → sector mapping used for sentiment bucketing
SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "Banking":    ["bank", "rbi", "credit", "loan", "npa", "nbfc", "interest rate", "repo", "hdfc", "icici", "sbi", "kotak"],
    "IT":         ["software", "tech", "it sector", "infosys", "tcs", "wipro", "digital", "ai ", "cloud", "outsourcing"],
    "Energy":     ["reliance", "oil", "gas", "petroleum", "crude", "refinery", "ongc", "fuel"],
    "FMCG":       ["fmcg", "consumer goods", "itc", "hindustan unilever", "hindunilvr", "fmcg", "packaged food", "beverages"],
    "Pharma":     ["pharma", "drug", "medicine", "healthcare", "hospital", "sunpharma", "cipla", "fda", "api"],
    "Auto":       ["auto", "vehicle", "car", "ev", "electric vehicle", "maruti", "two-wheeler", "passenger vehicle"],
    "Telecom":    ["telecom", "5g", "jio", "airtel", "bharti", "spectrum", "mobile data"],
    "Metals":     ["steel", "metal", "iron ore", "tata steel", "commodity", "aluminium", "copper"],
    "Realty":     ["real estate", "dlf", "property", "housing", "realty", "home loan"],
    "Finance":    ["bajaj finance", "bajfinance", "mutual fund", "insurance", "market rally", "sensex", "nifty"],
    "Consumer":   ["titan", "jewellery", "retail", "asian paints", "asianpaint", "consumer spending"],
}


class NewsFetcher:
    """Class to fetch and structure news data for LLM consumption."""

    BASE_URL = "https://newsdata.io/api/1/news"

    def __init__(self, api_key: str = None):
        """Initialize the NewsFetcher with the provided API key."""
        if not api_key:
            logger.warning("NEWS_API_KEY is missing! NewsFetcher might fail unless you provide a valid API key.")
        self.api_key = api_key
        self._analyzer = SentimentIntensityAnalyzer() if _VADER_AVAILABLE else None

    def get_latest_indian_business_news(self, max_articles: int = 15) -> str:
        """
        Fetches the latest Indian business news.
        
        Args:
            max_articles: Maximum number of articles to process. Default is 15
                          to avoid overwhelming the LLM prompt.
                             
        Returns:
            A formatted string containing news headlines and summaries, optimized for LLM prompting.
        """
        if not self.api_key or self.api_key == "your_newsdata_api_key_here":
            logger.error("Invalid NEWS_API_KEY. Please update .env file.")
            return "Error: Invalid or missing NewsData API key."
            
        logger.info("Fetching latest Indian business news from NewsData.io...")
        
        params = {
            "apikey": self.api_key,
            "country": "in",
            "category": "business",
            "language": "en"
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                logger.error(f"NewsData.io API returned an error: {data}")
                return "Error: Unable to fetch news. API returned failure status."
                
            results = data.get("results", [])
            if not results:
                logger.warning("No news results found for India business category.")
                return "No recent business news found."
                
            # Take the top N articles to keep context window manageable
            top_articles = results[:max_articles]
            
            formatted_news = []
            for i, article in enumerate(top_articles, 1):
                title = article.get("title", "").strip() if article.get("title") else "No Title"
                description = article.get("description", "")
                
                # Truncate description to keep context concise
                if description:
                    description = description.strip()
                    if len(description) > 300:
                        description = description[:300] + "..."
                
                pub_date = article.get("pubDate", "Unknown Date")
                
                news_item = f"Article {i}:\nTitle: {title}\nDate: {pub_date}"
                if description and description.lower() != "none...":
                    news_item += f"\nSummary: {description}"
                
                formatted_news.append(news_item)
                
            final_news_text = "\n\n".join(formatted_news)
            logger.info(f"Successfully fetched and formatted {len(top_articles)} news articles.")
            return final_news_text
            
        except requests.exceptions.Timeout:
            logger.error("Request to NewsData.io timed out.")
            return "Error: Request to News fetcher timed out."
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while fetching news: {e}")
            return f"Error: Failed to retrieve news due to network exception: {e}"
        except Exception as e:
            logger.error(f"Unexpected error in NewsFetcher: {e}")
            return f"Error: An unexpected exception occurred: {e}"

    def get_sector_sentiment(self, news_text: str) -> str:
        """
        Scores news sentiment per sector using VADER and returns a formatted string
        for inclusion in the AI prompt.

        Each sector gets a compound score in [-1.0, +1.0]:
          > +0.1  → BULLISH
          < -0.1  → BEARISH
          else    → NEUTRAL

        Args:
            news_text: The formatted news string already fetched.

        Returns:
            A formatted multi-line string like:
            "Banking: BULLISH (+0.42) | IT: NEUTRAL (+0.05) | ..."
        """
        if not self._analyzer or not news_text:
            return "Sentiment analysis unavailable."

        text_lower = news_text.lower()
        scores: Dict[str, float] = {}

        for sector, keywords in SECTOR_KEYWORDS.items():
            # Collect all sentences/lines that mention any keyword for this sector
            relevant_snippets = []
            for line in news_text.split("\n"):
                line_lower = line.lower()
                if any(kw in line_lower for kw in keywords):
                    relevant_snippets.append(line.strip())

            if not relevant_snippets:
                continue

            combined = " ".join(relevant_snippets[:10])  # cap to avoid overloading VADER
            compound = self._analyzer.polarity_scores(combined)["compound"]
            scores[sector] = round(compound, 3)

        if not scores:
            return "No sector-specific news found for sentiment scoring."

        lines = ["=== Sector Sentiment Scores (VADER) ==="]
        for sector, score in sorted(scores.items(), key=lambda x: -abs(x[1])):
            if score > 0.1:
                label = "BULLISH"
            elif score < -0.1:
                label = "BEARISH"
            else:
                label = "NEUTRAL"
            lines.append(f"  {sector}: {label} ({score:+.3f})")

        return "\n".join(lines)


if __name__ == "__main__":
    # Local execution testing
    fetcher = NewsFetcher()
    news_text = fetcher.get_latest_indian_business_news()
    print("=== LATEST NEWS TEXT ===\n")
    print(news_text)
    print("\n=== SECTOR SENTIMENT ===\n")
    print(fetcher.get_sector_sentiment(news_text))
