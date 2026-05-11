
import logging
import requests

logger = logging.getLogger("SATURDAY.Services.WebSearch")

class WebSearchService:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.event_bus.subscribe("search_request", self._on_search)
        logger.info("WebSearchService ready (DuckDuckGo IA API).")

    def _on_search(self, payload: dict):
        query = (payload or {}).get("query", "").strip()
        if not query:
            logger.warning("Search requested with empty query.")
            return
        results = self.search(query)
        if not results:
            self.event_bus.publish("voice_response", f"I couldn't find anything for {query}.")
            return

        top = results[0]
        spoken = f"Top result: {top['title']}. {top['snippet']}"
        self.event_bus.publish("voice_response", spoken)
        self.event_bus.publish("search_results", {"query": query, "results": results})

    def search(self, query: str, max_results: int = 5):
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        try:
            resp = requests.get(url, params=params, timeout=6)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        results = []

        for item in data.get("RelatedTopics", []):
            if "Text" in item and "FirstURL" in item:
                results.append({
                    "title": item.get("Text").split(" - ")[0],
                    "snippet": item.get("Text"),
                    "url": item.get("FirstURL")
                })
                if len(results) >= max_results:
                    break

        if not results and data.get("AbstractText"):
            results.append({
                "title": data.get("Heading") or query,
                "snippet": data.get("AbstractText"),
                "url": data.get("AbstractURL") or ""
            })

        return results
