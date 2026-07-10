import httpx
import trafilatura
import structlog
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class ScrapedContent:
    url: str
    text: str
    title: str | None = None


class WebScraper:

    async def extract(self, url: str) -> ScrapedContent | None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=15.0, follow_redirects=True)
                text = trafilatura.extract(
                    response.text,
                    include_comments=False,
                    include_tables=True,
                    favor_precision=True,
                )
                if not text:
                    return None
                return ScrapedContent(url=url, text=text)
            except Exception as e:
                logger.error("web_scrape_failed", url=url, error=str(e))
                return None
