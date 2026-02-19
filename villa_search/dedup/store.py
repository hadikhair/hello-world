"""
Déduplication des annonces via un fichier JSON persistant.

Stratégie double :
  1. Hash exact (URL + titre + prix)  → détecte les doublons stricts
  2. Similarité titre + prix ±5%      → détecte la même annonce repostée
"""

import json
import logging
import re
from pathlib import Path
from difflib import SequenceMatcher

from villa_search.models import Listing

logger = logging.getLogger(__name__)

STORE_FILE = Path(__file__).parent.parent / "data" / "seen_listings.json"


class DeduplicationStore:
    def __init__(self, store_path: Path = STORE_FILE):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if self.store_path.exists():
            try:
                with open(self.store_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self):
        with open(self.store_path, "w") as f:
            json.dump(self._seen, f, indent=2, default=str)

    def is_duplicate(self, listing: Listing) -> bool:
        """
        Retourne True si l'annonce a déjà été vue.
        Marque automatiquement comme vue si nouvelle.
        """
        # 1. Hash exact
        if listing.id in self._seen:
            logger.debug(f"Doublon exact: {listing.id} ({listing.url})")
            return True

        # 2. Similarité titre + prix proche
        normalized_title = self._normalize(listing.title)
        for seen_id, meta in self._seen.items():
            seen_title = self._normalize(meta.get("title", ""))
            seen_price = meta.get("price_mad")

            title_sim = SequenceMatcher(None, normalized_title, seen_title).ratio()
            price_close = self._prices_close(listing.price_mad, seen_price)

            if title_sim > 0.85 and price_close:
                logger.info(
                    f"Doublon similaire détecté: '{listing.title}' ≈ '{meta.get('title')}' "
                    f"(similarité={title_sim:.2f})"
                )
                return True

        return False

    def mark_seen(self, listing: Listing):
        self._seen[listing.id] = {
            "title": listing.title,
            "price_mad": listing.price_mad,
            "url": listing.url,
            "source": listing.source,
            "scraped_at": listing.scraped_at.isoformat(),
        }
        self._save()

    def filter_new(self, listings: list[Listing]) -> list[Listing]:
        """Filtre et retourne uniquement les annonces nouvelles."""
        new = []
        for listing in listings:
            if not self.is_duplicate(listing):
                listing.is_new = True
                self.mark_seen(listing)
                new.append(listing)
            else:
                listing.is_new = False
        logger.info(f"Déduplication: {len(new)}/{len(listings)} nouvelles annonces.")
        return new

    def total_seen(self) -> int:
        return len(self._seen)

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _prices_close(p1, p2, tolerance: float = 0.05) -> bool:
        if p1 is None or p2 is None:
            return False
        diff = abs(p1 - p2) / max(p1, p2)
        return diff <= tolerance
