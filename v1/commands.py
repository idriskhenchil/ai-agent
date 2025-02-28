from news import News
from mistralai import Mistral
from loguru import logger
import randfacts
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

mistral = Mistral(os.getenv("API_KEY"))

class Command:
    def __init__(self):
        print(f"Loading:\nHere's a fact while your news loads:\n{randfacts.get_fact()}")

    def help(self):
        return """
📰 News Bot Help 📰
To use the News Bot, enter one of the following commands:
        
Available Commands:
- !news [category]           - Get news articles by category (get_topic(category))
- !news brief                - Get a brief summary of top headlines (brief)
- !news source <source>      - List or filter by specific news sources (get_source(source))
- !news compare <topic>      - Compare coverage of a topic across sources (compare(topic))
- !news bias <topic>         - Analyze potential bias in coverage of a topic 
- !news summarize [category] - Get summarized news articles (summarize(category))
        """


    def top(self):
        """Get top headlines."""
        
        prompt = (
            f"Create a concise daily news brief from these articles. "
            f"Format as '📰 TOP NEWS 📰' followed by 3-5 key headlines with 1-2 sentence summaries for each. "
            f"Here is the content:\n{News.top()}"
        )
        
        try:
            resp = mistral.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Error fetching brief | error: {e}")


    def brief(self):
        """Get a brief summary of top headlines."""
        
        prompt = (
            f"Create a concise daily news brief from these articles. "
            f"Format as '📰 NEWS BRIEF 📰' followed by a paragraph summary "
            f"Here is the content:\n{News.top()}"
        )
        
        try:
            resp = mistral.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Error fetching brief | error: {e}")

    def get_topic(self, topic: str):
        prompt = (
            f"Display these articles in a listed format "
            f"Format as '📰 {topic.upper()} NEWS 📰' followed by 3-5 key headlines with 1-2 sentence summaries for each. "
            f"Here is the content:\n{News.get_topic(topic)}"
        )
        
        try:
            resp = mistral.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Error fetching brief | error: {e}")


    def get_source(self, url: str):
        """
        Attempts to get a specified news source such as cnn.com or nytimes.com
        """
        prompt = (
            f"Display these articles in a listed format "
            f"Format as '📰 {url.upper()} NEWS 📰' followed by 3-5 key headlines with 1-2 sentence summaries for each. "
            f"Here is the content:\n{News.specific_source(url)}"
        )
        
        try:
            resp = mistral.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Error fetching brief | error: {e}")
        
    def compare(self, topic: str):
        """Compare coverage of a topic across different news sources."""

        prompt = (
            f"Compare the following news coverage for the topic '{topic}' by different publishers. "
            f"Format as '📰 {topic.upper()} NEWS 📰' followed any notable differences or similarities in the headlines with 1-2 sentence summaries for each. "
            f"Here is the data:\n{News.get_topic(topic)}\n"
            f"Provide a brief analysis."
        )
        resp = mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    

    def summarize(self, topic: str):
        """Summarize news articles (using title and description)."""

        prompt = (
            f"Summarize the following articles in 1 small paragraph:\n\n{News.get_topic(topic)}\n\nBegin your summary now:"
            f"Format as '📰 {topic.upper()} NEWS SUMMARY 📰'"
        )
        resp = mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    

    def bias(self, topic: str):
        """Analyze potential bias in the coverage of a topic."""

        prompt = (
            f"Analyze the potential bias in the following news headlines on the topic '{topic}'. "
            f"Format as '📰 {topic.upper()} NEWS BIAS 📰'"
            f"Consider the choice of words, the sources, and any political or cultural leanings that may be inferred. "
            f"Here are the headlines:\n{News.get_topic(topic)}\n"
            f"Provide your analysis in a concise summary."
        )
        resp = mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    

if __name__ == "__main__":
    print(Command().top())
    # print(Command().brief())
    # print(Command().get_topic("world"))
    # print(Command().get_source("cnn.com"))
    # print(Command().compare("sports"))
    # print(Command().summarize("world"))
    # print(Command().bias("world"))
        