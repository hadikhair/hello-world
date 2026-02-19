import hashlib
import logging
import time
import random
from abc import ABC, abstractmethod
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from villa_search.models import Listing

logger = logging.getLogger(__name__)

# Headers réalistes pour éviter le blocage
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-MA,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper(ABC):
    source_name: str = "unknown"
    delay_range: tuple[float, float] = (1.5, 4.0)

    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def polite_get(self, url: str, **kwargs) -> requests.Response:
        """GET avec délai aléatoire pour ne pas surcharger les serveurs."""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        try:
            resp = self.session.get(url, timeout=15, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f"[{self.source_name}] Erreur fetch {url}: {e}")
            raise

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def make_fingerprint(*parts: str) -> str:
        """Hash déterministe pour identifier une annonce de façon unique."""
        key = "|".join(str(p).strip().lower() for p in parts if p)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def parse_price(raw: str) -> int | None:
        """Extrait un entier depuis une chaîne de prix MAD."""
        import re
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None

    @staticmethod
    def parse_int(raw: str) -> int | None:
        import re
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None

    @abstractmethod
    def search_pages(self) -> Iterator[Listing]:
        """Yield des Listing depuis toutes les pages de résultats."""
        ...
