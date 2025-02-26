import os
from mistralai import Mistral
import discord
import feedparser
import json
import aiohttp
import asyncio
from datetime import datetime, timedelta

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = """You are a helpful news assistant. Your role is to:
1. Help users find the latest news on various topics
2. Summarize news articles
3. Provide trend analysis across news sources
4. Answer questions about current events
5. Organize news by category
Be concise and informative in your responses."""

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.news_sources = {
            "technology": ["https://techcrunch.com/feed/", "https://www.wired.com/feed/rss"],
            "business": ["https://www.cnbc.com/id/10001147/device/rss/rss.html"],
            "politics": ["https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"],
            "science": ["https://www.science.org/rss/news_feeds/toc_science.xml"],
            "general": ["https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"]
        }
        self.news_cache = {}
        self.last_fetch = {}
        
    async def fetch_news(self, category="general", force_refresh=False):
        """Fetch news from RSS feeds for a specific category"""
        # Check if we need to refresh the cache
        now = datetime.now()
        if (category in self.last_fetch and 
            now - self.last_fetch[category] < timedelta(hours=1) and 
            not force_refresh):
            return self.news_cache.get(category, [])
        
        sources = self.news_sources.get(category, self.news_sources["general"])
        all_entries = []
        
        for source_url in sources:
            try:
                feed = feedparser.parse(source_url)
                for entry in feed.entries[:5]:  # Get the top 5 from each source
                    all_entries.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", "Unknown date"),
                        "source": feed.feed.title,
                        "summary": entry.get("summary", "No summary available")
                    })
            except Exception as e:
                print(f"Error fetching from {source_url}: {e}")
                
        # Update cache and last fetch time
        self.news_cache[category] = all_entries
        self.last_fetch[category] = now
        return all_entries
    
    async def summarize_article(self, url):
        """Fetch and summarize a specific article"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    
                # Use Mistral API to summarize the article
                messages = [
                    {"role": "system", "content": "Summarize the following news article in 3-4 concise bullet points."},
                    {"role": "user", "content": f"Article URL: {url}\n\nContent: {html[:4000]}..."}  # Truncate to avoid token limits
                ]
                
                response = await self.client.chat.complete_async(
                    model=MISTRAL_MODEL,
                    messages=messages,
                )
                
                return response.choices[0].message.content
            except Exception as e:
                return f"Error summarizing article: {e}"
    
    async def process_command(self, message_content):
        """Process news-related commands"""
        content = message_content.lower()
        
        if content.startswith("news "):
            parts = content[5:].split()
            
            if not parts:
                # Default to general news
                news = await self.fetch_news("general")
                return self.format_news_response(news, "general")
            
            command = parts[0]
            
            if command in self.news_sources:
                # Category request
                news = await self.fetch_news(command)
                return self.format_news_response(news, command)
            
            elif command == "summary" and len(parts) > 1:
                # Article summary request
                url = parts[1]
                return await self.summarize_article(url)
            
            elif command == "refresh":
                # Force refresh all categories
                for category in self.news_sources:
                    await self.fetch_news(category, force_refresh=True)
                return "News sources refreshed!"
            
            else:
                # Treat as a search query
                # For simplicity, we'll just fetch general news and let Mistral filter
                news = await self.fetch_news("general")
                query = " ".join(parts)
                return await self.search_news(news, query)
        
        return None  # Not a news command
        
    def format_news_response(self, news_items, category):
        """Format news items into a readable Discord message"""
        if not news_items:
            return f"No recent news found for {category}."
            
        response = f"📰 **LATEST {category.upper()} NEWS** 📰\n\n"
        
        for i, item in enumerate(news_items[:5], 1):  # Top 5 items
            response += f"{i}. **{item['title']}**\n"
            response += f"   Source: {item['source']} | {item['published']}\n"
            response += f"   Link: {item['link']}\n\n"
            
        response += "Use `news summary <url>` to get a summary of any article."
        return response
        
    async def search_news(self, news_items, query):
        """Search for news matching a query using Mistral's capabilities"""
        if not news_items:
            return "No news items available to search."
            
        # Format news items as context
        news_context = ""
        for i, item in enumerate(news_items, 1):
            news_context += f"{i}. Title: {item['title']}\n"
            news_context += f"   Summary: {item['summary'][:100]}...\n"
            news_context += f"   Link: {item['link']}\n\n"
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"I'm looking for news about '{query}'. Here are the latest headlines:\n\n{news_context}\n\nPlease find and list the most relevant articles to my query. Include the article numbers and links."}
        ]
        
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        
        return response.choices[0].message.content

    async def run(self, message: discord.Message):
        """Process a Discord message and return a response"""
        # Check if this is a news command
        news_response = await self.process_command(message.content)
        if news_response:
            return news_response
        
        # Otherwise, treat as a general query to the AI
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content},
        ]
        
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        
        return response.choices[0].message.content