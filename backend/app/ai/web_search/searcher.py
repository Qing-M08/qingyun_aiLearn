import httpx
import structlog
from dataclasses import dataclass

from app.config import settings

logger = structlog.get_logger()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearcher:

    def __init__(self):
        self.api_key = settings.BING_SEARCH_API_KEY

    async def search(self, query: str, num_results: int = 10) -> list[SearchResult]:
        if not self.api_key:
            logger.warning("bing_api_key_not_configured")
            return []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    params={"q": query, "count": num_results, "mkt": "zh-CN"},
                    timeout=10.0,
                )
                data = response.json()
                return [
                    SearchResult(
                        title=item["name"],
                        url=item["url"],
                        snippet=item.get("snippet", ""),
                    )
                    for item in data.get("webPages", {}).get("value", [])
                ]
            except Exception as e:
                logger.error("web_search_failed", error=str(e))
                return []
