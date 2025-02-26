import os
import logging
import requests
from dotenv import load_dotenv
from mistralai import Mistral
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Load environment variables
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Setup logging to file only, not console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='news_summary.log',  # Log to file instead of console
    filemode='a'  # Append mode
)
logger = logging.getLogger("news_summary")

# Suppress other loggers that might print to console
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# Mistral client
mistral = Mistral(api_key=MISTRAL_API_KEY)

def get_news_sources(query):
    """Uses Mistral to suggest reputable news sources."""
    logger.info(f"Querying Mistral for news sources related to: {query}")
    
    prompt = f"List three reputable news sources for {query}."
    response = mistral.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": prompt}]
    )
    
    sources_text = response.choices[0].message.content
    logger.info(f"Raw Mistral response: {sources_text}")
    
    # Filter out empty lines and strip whitespace
    sources = [source.strip() for source in sources_text.split("\n") if source.strip()]
    logger.info(f"Sources found: {sources}")
    return sources

def get_news_urls(query):
    """Fetches news URLs directly from Google News."""
    logger.info(f"Fetching news URLs for topic: {query}")
    
    # Try direct HTML scraping instead of RSS
    search_url = f"https://news.google.com/search?q={query}&hl=en-US"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find article links - Google News has links with specific attributes
        article_links = []
        
        # Look for article links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            
            # Google News article links usually start with './articles'
            if href.startswith('./articles'):
                full_url = 'https://news.google.com' + href[1:]  # Remove the leading dot
                article_links.append(full_url)
                
        logger.info(f"Found {len(article_links)} article links from Google News")
        
        # If we don't have enough links, try an alternative approach
        if len(article_links) < 3:
            # Try to use a backup news API
            backup_api_url = f"https://newsapi.org/v2/everything?q={query}&apiKey=YOUR_API_KEY"
            logger.info("Insufficient links found. You might want to consider using a news API like NewsAPI.org")
            
            # For now, let's try a fallback to search engine results
            fallback_search_url = f"https://www.bing.com/news/search?q={query}"
            fallback_response = requests.get(fallback_search_url, headers=headers, timeout=15)
            fallback_soup = BeautifulSoup(fallback_response.text, "html.parser")
            
            for a_tag in fallback_soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                # Filter for news article links (usually have http or https)
                if href.startswith(('http://', 'https://')) and 'bing' not in href and 'microsoft' not in href:
                    article_links.append(href)
                    if len(article_links) >= 5:
                        break
            
            logger.info(f"After fallback search, found {len(article_links)} total links")
                
        # Take the first 5 unique links
        unique_links = []
        seen = set()
        
        for link in article_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
                if len(unique_links) >= 5:
                    break
                    
        logger.info(f"Returning {len(unique_links)} unique article URLs")
        return unique_links
        
    except Exception as e:
        logger.error(f"Error fetching news URLs: {e}")
        
        # Last resort: try the RSS feed method as backup
        try:
            logger.info("Attempting RSS feed method as backup")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            rss_response = requests.get(rss_url, timeout=10)
            rss_response.raise_for_status()
            
            rss_soup = BeautifulSoup(rss_response.content, 'xml')
            items = rss_soup.find_all('item')
            backup_urls = []
            
            for item in items[:5]:
                if item.find('link'):
                    link = item.find('link').text.strip()
                    if link.startswith(('http://', 'https://')):
                        backup_urls.append(link)
            
            logger.info(f"Found {len(backup_urls)} URLs from RSS feed")
            
            if backup_urls:
                return backup_urls
                
            # If we still don't have URLs, try one more option - search directly
            # Use the sources we got from Mistral to help find content
            if sources:
                logger.info(f"Attempting to use suggested sources: {sources}")
                for source in sources:
                    # Try to extract domain name or site name from Mistral's suggestion
                    for word in source.split():
                        # Clean up the word and check if it might be a news source name
                        clean_word = word.lower().strip('.,:**')
                        if len(clean_word) > 3 and clean_word not in ['news', 'the', 'and', 'for']:
                            search_term = f"{clean_word} {query} news"
                            search_url = f"https://www.google.com/search?q={search_term}"
                            
                            try:
                                search_response = requests.get(search_url, headers=headers, timeout=10)
                                search_soup = BeautifulSoup(search_response.text, "html.parser")
                                
                                # Extract links
                                for a_tag in search_soup.find_all('a', href=True):
                                    href = a_tag.get('href', '')
                                    if href.startswith('/url?q='):
                                        # Extract actual URL from Google redirect
                                        actual_url = href.split('/url?q=')[1].split('&')[0]
                                        if actual_url.startswith(('http://', 'https://')) and 'google' not in actual_url:
                                            backup_urls.append(actual_url)
                                            if len(backup_urls) >= 5:
                                                return backup_urls
                            except Exception as search_error:
                                logger.error(f"Error in source-based search: {search_error}")
                                
            return backup_urls
        except Exception as backup_error:
            logger.error(f"Backup RSS method also failed: {backup_error}")
            return []

def scrape_article(url):
    """Enhanced function to scrape article text from a given URL."""
    logger.info(f"Scraping article from: {url}")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        
        # Check if we got a valid response
        if response.status_code != 200:
            logger.warning(f"Received status code {response.status_code} from {url}")
            return ""
        
        # Try to detect and handle paywalls or subscription walls
        paywall_detected = any(term in response.text.lower() for term in ['subscribe', 'subscription', 'paywall', 'premium'])
        if paywall_detected:
            logger.warning(f"Possible paywall detected at {url}")
        
        # Special handling for MSN.com
        if 'msn.com' in url:
            logger.info("Applying special handling for MSN.com")
            try:
                # MSN.com stores article content in JSON-LD format
                import json
                import re
                
                # Try to extract the article content from the JSON-LD
                json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL)
                if json_ld_match:
                    json_ld = json_ld_match.group(1).strip()
                    try:
                        article_data = json.loads(json_ld)
                        
                        # Extract article content
                        if isinstance(article_data, dict):
                            if 'articleBody' in article_data:
                                return article_data['articleBody'][:5000]
                            elif 'description' in article_data:
                                return article_data['description'][:5000]
                    except json.JSONDecodeError:
                        pass
                
                # If JSON-LD extraction failed, try to get the headline at least
                soup = BeautifulSoup(response.text, "html.parser")
                headline = soup.find('h1')
                if headline:
                    headline_text = headline.get_text().strip()
                    
                    # Try to extract article container specific to MSN
                    article_container = soup.find('div', class_='articlecontent')
                    if article_container:
                        paragraphs = article_container.find_all('p')
                        article_text = " ".join([p.get_text().strip() for p in paragraphs])
                        if article_text:
                            logger.info(f"Successfully extracted MSN article content: {len(article_text)} chars")
                            return headline_text + ". " + article_text
                    
                    # Get the meta description if nothing else works
                    meta_desc = soup.find('meta', {'name': 'description'})
                    if meta_desc and meta_desc.get('content'):
                        return headline_text + ". " + meta_desc.get('content')
                    
                    # Return just the headline if nothing else works
                    return headline_text
            except Exception as msn_error:
                logger.error(f"MSN special handling error: {msn_error}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract title for minimum content
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        # Also try to get meta description
        meta_desc = ""
        meta_tag = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
        if meta_tag and meta_tag.get('content'):
            meta_desc = meta_tag.get('content').strip()
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()
            
        # Try multiple methods to extract the article content
        article_text = ""
        
        # Method 1: Try data-testid attributes (common in many news sites)
        article = soup.find(attrs={"data-testid": lambda x: x and "article" in x.lower() if x else False})
        
        # Method 2: Look for article tag
        if not article or not article.text.strip():
            article = soup.find("article")
        
        # Method 3: Look for common content containers
        if not article or not article.text.strip():
            for class_hint in ["article", "content", "main", "story", "entry", "post", "text", "body"]:
                article = soup.find(class_=lambda x: x and class_hint in x.lower() if x else False)
                if article and article.text.strip():
                    break
        
        # Method 4: Look for main tag
        if not article or not article.text.strip():
            article = soup.find("main")
            
        # Method 5: Look for largest div with multiple paragraphs
        if not article or not article.text.strip():
            divs = soup.find_all("div")
            candidate = None
            max_p_count = 0
            
            for div in divs:
                p_count = len(div.find_all("p"))
                if p_count > max_p_count:
                    max_p_count = p_count
                    candidate = div
                    
            if max_p_count >= 3:  # At least 3 paragraphs
                article = candidate
        
        # Extract text from the identified container
        if article and article.text.strip():
            # Get all paragraphs
            paragraphs = article.find_all("p")
            
            # Filter out short paragraphs (likely not content)
            content_paragraphs = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20]
            
            if content_paragraphs:
                article_text = " ".join(content_paragraphs)
            else:
                # Fallback: just get the text from the article container
                article_text = article.get_text().strip()
        
        # Last resort: get all paragraphs from the page
        if not article_text:
            paragraphs = soup.find_all("p")
            content_paragraphs = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
            article_text = " ".join(content_paragraphs)
        
        # Clean up the text
        # Remove excessive whitespace
        article_text = ' '.join(article_text.split())
        
        # If we still don't have enough content, use the title and meta description
        if len(article_text) < 100:
            if title or meta_desc:
                logger.info("Using title and meta description as fallback")
                if title and meta_desc:
                    return f"{title}. {meta_desc}"
                return title or meta_desc
            
            # Try to get headings as a last resort
            headings = [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3'])]
            if headings:
                logger.info("Using headings as fallback")
                return " ".join(headings)
        
        logger.info(f"Scraped {len(article_text)} characters from {url}")
        
        # Ensure we have some content
        if not article_text and (title or meta_desc):
            article_text = f"{title}. {meta_desc}"
        
        # Return truncated text for API limits
        if article_text:
            return article_text[:5000]
        
        # Absolute last resort - return the URL itself with a note
        return f"Article from {url}. Unable to extract full content due to possible paywall or site restrictions."
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        # Even on error, try to return something useful
        domain = url.split('//')[-1].split('/')[0]
        return f"Article from {domain}. Unable to extract content."

def summarize_news(articles):
    """Uses Mistral to summarize multiple articles into a longer, multi-paragraph format."""
    logger.info("Summarizing articles...")
    
    if not articles:
        return "No valid articles found to summarize."
    
    # Validate articles - ensure we have actual content
    valid_articles = [article for article in articles if len(article.strip()) > 50]
    
    if not valid_articles:
        logger.warning("No valid articles with sufficient content found")
        # Use whatever we have
        valid_articles = articles
    
    # Print article lengths for debugging
    for i, article in enumerate(valid_articles):
        logger.info(f"Article {i+1} length: {len(article)} characters")
        # Log first 100 chars of each article for debugging
        logger.info(f"Article {i+1} preview: {article[:100]}...")
        
    # Create a more compact combined text to save tokens
    combined_text = "\n\n---ARTICLE---\n\n".join(valid_articles)
    
    # Create a more focused prompt for longer summaries
    prompt = f"""You are a professional news analyst. The following are excerpts from news articles about the same topic.
Please create a comprehensive summary that captures all key information from these articles.

Requirements for the summary:
1. Length: Between 250-500 words total
2. Structure: Divide the summary into exactly 3 paragraphs
   - First paragraph: Introduce the main news event and key facts
   - Second paragraph: Provide context, background details, and supporting information
   - Third paragraph: Include reactions, implications, or future perspectives
3. Style: Factual, objective, and journalistic
4. Content: Integrate all important details from the articles without redundancy

Articles:
{combined_text}

Begin your summary now:"""

    try:
        response = mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        
        summary = response.choices[0].message.content
        logger.info(f"Generated summary length: {len(summary.split())} words")
        
        # Validate summary - if it contains certain phrases indicating missing content
        indicators = ["missing", "no article", "couldn't find", "no content", "please provide"]
        if any(indicator in summary.lower() for indicator in indicators):
            logger.warning("Summary indicates missing content, generating alternate summary")
            # Create an alternate summary from what we have
            alt_prompt = f"""You are a news writer tasked with creating a comprehensive summary based on limited information.
Using only the facts available in these partial article fragments, write a detailed news summary.

Requirements:
1. Length: Between 250-500 words total
2. Structure: Exactly 3 paragraphs with clear breaks between them
3. Style: Factual and journalistic
4. Content: Focus only on the information that is definitely available in the fragments

Article fragments:
{combined_text}

Write your 3-paragraph summary:"""
            
            alt_response = mistral.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": alt_prompt}]
            )
            
            summary = alt_response.choices[0].message.content
            logger.info(f"Generated alternate summary length: {len(summary.split())} words")
            
        # Ensure the summary has proper paragraph breaks
        if summary.count('\n\n') < 2:
            # Try to split into paragraphs if not already formatted correctly
            sentences = summary.split('. ')
            if len(sentences) >= 6:
                third = len(sentences) // 3
                para1 = '. '.join(sentences[:third]) + '.'
                para2 = '. '.join(sentences[third:2*third]) + '.'
                para3 = '. '.join(sentences[2*third:])
                
                # Ensure last paragraph ends with period if needed
                if not para3.endswith('.'):
                    para3 += '.'
                    
                summary = f"{para1}\n\n{para2}\n\n{para3}"
                logger.info("Reformatted summary into 3 paragraphs")
            
        return summary
        
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
        # Try to create a basic summary without AI
        try:
            # Basic multi-paragraph summary from titles and content
            sentences = []
            for article in valid_articles:
                # Split into sentences
                article_sentences = [s.strip() + '.' for s in article.split('.') if s.strip()]
                sentences.extend(article_sentences[:5])  # Take up to 5 sentences from each article
            
            if sentences:
                third = max(1, len(sentences) // 3)
                para1 = ' '.join(sentences[:third])
                para2 = ' '.join(sentences[third:2*third])
                para3 = ' '.join(sentences[2*third:3*third])
                
                return f"{para1}\n\n{para2}\n\n{para3}"
            else:
                return "Insufficient content available to generate a summary."
        except:
            return "Error generating summary. Please try again with a different news topic."

def main():
    try:
        topic = input("Enter a news topic: ")
        logger.info(f"Starting news summary process for topic: {topic}")
        
        # Get news sources
        sources = get_news_sources(topic)
        
        # Get news URLs
        urls = get_news_urls(topic)
        if not urls:
            print("Couldn't retrieve any news URLs. Try a different topic or check your internet connection.")
            return
            
        # Scrape articles 
        articles = []
        for i, url in enumerate(urls, 1):
            article_text = scrape_article(url)
            if article_text:
                articles.append(article_text)
                
        if not articles:
            print("Couldn't retrieve any article content. Try a different topic.")
            return
            
        # Generate summary
        summary = summarize_news(articles)
        
        # Print only the final summary
        #print("\n===== NEWS SUMMARY =====")
        print(summary)
        #print("========================\n")
        
        # Print word count
        #word_count = len(summary.split())
        #print(f"Word count: {word_count} words\n")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()