"""
News Fetcher module for rupee50k-ai-sector-trader.
Retrieves the latest business and economic news for India using NewsData.io API.
"""

import requests
from config import NEWS_API_KEY, logger

class NewsFetcher:
    """Class to fetch and structure news data for LLM consumption."""
    
    BASE_URL = "https://newsdata.io/api/1/news"
    
    def __init__(self, api_key: str = NEWS_API_KEY):
        """Initialize the NewsFetcher with the provided API key."""
        if not api_key:
            logger.warning("NEWS_API_KEY is missing! NewsFetcher might fail unless you provide a valid API key.")
        self.api_key = api_key

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

if __name__ == "__main__":
    # Local execution testing
    fetcher = NewsFetcher()
    news_text = fetcher.get_latest_indian_business_news()
    print("=== LATEST LATEST NEWS TEXT ===\n")
    print(news_text)
