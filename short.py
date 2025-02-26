import os
import logging
import requests
from dotenv import load_dotenv
from mistralai import Mistral
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="news_summary.log",
    filemode="a",
)
logger = logging.getLogger("news_summary")

mistral = Mistral(api_key=MISTRAL_API_KEY)

def get_news_urls(query):
    """
    Fetch up to 5 news article URLs using Bing News search only.
    Removes Google News and RSS approaches to keep it minimal.
    """
    logger.info(f"Fetching news URLs from Bing for: {query}")
    headers = {"User-Agent": "Mozilla/5.0"}
    article_links = []

    try:
        bing_url = f"https://www.bing.com/news/search?q={query}"
        resp = requests.get(bing_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://")) and "bing" not in href:
                article_links.append(href)
    except:
        pass

    # Keep only first 5 unique URLs
    unique_links = []
    seen = set()
    for link in article_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
            if len(unique_links) >= 5:
                break

    return unique_links

def scrape_article(url):
    """
    Scrape text from an article with a robust container detection:
    tries <article>, <main>, or largest <div> with paragraphs.
    """
    logger.info(f"Scraping {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove irrelevant elements
        for tag in soup(["script","style","nav","footer","header","aside","iframe","noscript"]):
            tag.decompose()

        # Try <article>, <main>, then largest <div>
        container = soup.find("article")
        if not container or not container.get_text().strip():
            container = soup.find("main")
        if not container or not container.get_text().strip():
            divs = soup.find_all("div")
            max_div, max_p = None, 0
            for d in divs:
                p_count = len(d.find_all("p"))
                if p_count > max_p:
                    max_p = p_count
                    max_div = d
            container = max_div if max_div else None

        if container:
            paragraphs = [p.get_text().strip() for p in container.find_all("p") if p.get_text().strip()]
            text = " ".join(paragraphs)
        else:
            # Fallback: all paragraphs
            paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
            text = " ".join(paragraphs)

        return text[:5000] if text else ""
    except:
        return ""

def summarize_news(articles):
    """
    Summarize articles in 3 paragraphs using Mistral.
    """
    articles = [a for a in articles if a.strip()]
    if not articles:
        return "No articles found with content."
    
    combined_text = "\n---ARTICLE---\n".join(articles)
    prompt = (
        "Summarize the following articles in 3 paragraphs:\n\n"
        f"{combined_text}\n\n"
        "Begin your summary now:"
    )
    try:
        resp = mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    except:
        return "Error during summarization."

def main():
    topic = input("Enter a news topic: ")
    urls = get_news_urls(topic)
    if not urls:
        print("No URLs found. Try another topic.")
        return
    articles = [scrape_article(u) for u in urls]
    summary = summarize_news(articles)
    print(summary)

if __name__ == "__main__":
    main()
