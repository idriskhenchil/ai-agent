from gnews import GNews
from loguru import logger

google_news = GNews()

class News:
    def get_topic(topic: str, limit: int = 10) -> list:
        if topic:
            try:
                news = google_news.get_news(topic)
            except Exception as e:
                logger.error(f"Error fetching feed with topic {topic} | error: {e}")
        else:
            logger.error("Topic not provided")
        """
        Takes in a topic and returns a list of articles that contain
        title, description, published_date, url, publisher: {href, title}

        Default limit is 10 articles unless specified otherwise
        """
        results = []

        # only get up to 10 articles
        for article in news:
            results.append(article)

        return results
    
    def top() -> list:
        news = [x for x in google_news.get_top_news()][:10] 
        return news

    def specific_source(url: str) -> list:
        news = [x for x in google_news.get_news_by_site(site=url)][:10] 

        return news