# services/news_service.py
import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger("AEGIS.News")

class NewsService:
    """Fetches real headlines and falls back to cached data when offline."""
    def __init__(self):
        feed_urls = os.getenv(
            "AEGIS_NEWS_FEEDS",
            "https://feeds.reuters.com/reuters/worldNews,https://apnews.com/hub/ap-top-news/rss.xml",
        )
        self.feed_urls = [url.strip() for url in feed_urls.split(",") if url.strip()]
        self.cache_ttl_seconds = int(os.getenv("AEGIS_NEWS_CACHE_TTL_SECONDS", "900"))
        self.cached_headlines = []
        self.last_refresh = 0.0

    def get_latest(self):
        """Returns the latest real headline or a truthful fallback."""
        headlines = self._get_headlines()
        if headlines:
            return headlines[0]
        return "Live news is currently unavailable."

    async def fetch_real_news(self):
        """Async wrapper around the RSS fetcher."""
        loop = asyncio.get_running_loop()
        headlines = await loop.run_in_executor(None, self._refresh_headlines)
        if headlines:
            return headlines[0]
        return "Live news is currently unavailable."

    def _get_headlines(self):
        if self.cached_headlines and (time.time() - self.last_refresh) < self.cache_ttl_seconds:
            return self.cached_headlines
        return self._refresh_headlines()

    def _refresh_headlines(self):
        collected = []
        for feed_url in self.feed_urls:
            try:
                response = requests.get(feed_url, timeout=6)
                response.raise_for_status()
                collected.extend(self._parse_feed(response.text))
            except Exception as e:
                logger.warning("News feed fetch failed", feed_url=feed_url, error=str(e))
        unique = []
        seen = set()
        for headline in collected:
            if headline in seen:
                continue
            seen.add(headline)
            unique.append(headline)
        if unique:
            self.cached_headlines = unique[:10]
            self.last_refresh = time.time()
        return self.cached_headlines

    def _parse_feed(self, xml_text: str):
        headlines = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return headlines

        for item in root.findall(".//item/title"):
            title = (item.text or "").strip()
            if title:
                headlines.append(title)
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title"):
            title = (entry.text or "").strip()
            if title:
                headlines.append(title)
        return headlines
