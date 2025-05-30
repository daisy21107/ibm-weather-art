import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

api_key = os.getenv('GUARDIAN_API_KEY')
if not api_key:
    raise ValueError("GUARDIAN_API_KEY not found in environment variables. Please set it in .env file.")

class GuardianNewsAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://content.guardianapis.com/search"

    def build_api_url(self, query=None, page_size=5):
        """
        Formulate the API URL with query parameters.
        Args:
            query (str): Search query.
            page_size (int): Number of results to return.
        Returns:
            str: Formulated API URL.
        """
        params = {
            "api-key": self.api_key,
            "show-fields": "body",
            "page-size": page_size
        }
        if query:  # only add query if it's not None
            params["q"] = query

        query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{self.base_url}?{query_string}"

    def fetch_news(self, query=None, result_num=5):
        """
        Fetch news articles from the Guardian API.
        Args:
            query (str): Search query.
            result_num (int): Number of results to return.
        Returns:
            None
        """
        api_url = self.build_api_url(query, page_size=result_num)
        print(f"🔗 Fetching from: {api_url}\n")

        response = requests.get(api_url)
        if response.status_code != 200:
            print(f"❗ Failed to fetch: HTTP {response.status_code}")
            if response.status_code == 401:
                print("❗ Authentication failed. Please check your API key.")
            return

        data = response.json()
        if "response" not in data or not data["response"].get("results"):
            print("❗ No news entries found.")
            return

        results = data["response"]["results"]

        for entry in results:
            title = entry.get("webTitle", "[No Title]")
            link = entry.get("webUrl", "[No URL]")
            published = entry.get("webPublicationDate", "[No Date]")
            body = entry.get("fields", {}).get("body", "[No Body Content]")

            clean_body = BeautifulSoup(body, "html.parser").get_text() if body else "[No Body Content]"
            # only show first 5 sentences 
            preview_body = clean_body.split(".")
            preview_body = ".".join(preview_body[:5]) + ". ..." if preview_body else "[No Body Content]"

            print(f"📰 Title: {title}")
            print(f"🔗 Link: {link}")
            print(f"📅 Published: {published}")
            print(f"📄 Body (Preview):\n{preview_body}\n")
            print("-" * 80)

if __name__ == "__main__":
    news_fetcher = GuardianNewsAPI(api_key)
    query = input("🔍 Enter your search query (leave blank for latest news): ").strip()
    query = query if query else None
    news_fetcher.fetch_news(query=query, result_num=5)
