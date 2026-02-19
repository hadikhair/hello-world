"""
Filtre les annonces selon les critères de recherche configurés.

Règles appliquées dans l'ordre :
  1. Nombre de chambres
  2. Surface minimale
  3. Budget (min/max)
  4. Présence de mots-clés "moderne"
  5. Exclusion de mots-clés indésirables
  6. Score total minimum
"""

import logging
import re

from villa_search.models import Listing

logger = logging.getLogger(__name__)


class ListingFilter:
    def __init__(self, config: dict, min_score: float = 35.0):
        search = config.get("search", {})
        self.min_bedrooms: int = search.get("min_bedrooms", 4)
        self.max_bedrooms: int = search.get("max_bedrooms", 99)
        self.min_surface: int = search.get("min_surface_m2", 0)
        self.max_price: int = search.get("max_price_mad", 999_999_999)
        self.min_price: int = search.get("min_price_mad", 0)
        self.style_keywords: list[str] = [
            kw.lower() for kw in search.get("style_keywords", [])
        ]
        self.exclude_keywords: list[str] = [
            kw.lower() for kw in search.get("exclude_keywords", [])
        ]
        self.neighborhood: str = search.get("neighborhood", "").lower()
        self.min_score: float = min_score

    def passes(self, listing: Listing) -> tuple[bool, str]:
        """
        Retourne (True, "") si l'annonce passe, sinon (False, raison).
        """
        text = (listing.title + " " + listing.description).lower()

        # 1. Chambres
        if listing.bedrooms is not None:
            if not (self.min_bedrooms <= listing.bedrooms <= self.max_bedrooms):
                return False, f"{listing.bedrooms} chambres (attendu {self.min_bedrooms}-{self.max_bedrooms})"

        # 2. Surface
        if listing.surface_m2 is not None and listing.surface_m2 < self.min_surface:
            return False, f"Surface {listing.surface_m2}m² < minimum {self.min_surface}m²"

        # 3. Prix
        if listing.price_mad is not None:
            if listing.price_mad > self.max_price:
                return False, f"Prix {listing.price_mad:,} MAD > budget max {self.max_price:,} MAD"
            if listing.price_mad < self.min_price:
                return False, f"Prix {listing.price_mad:,} MAD < budget min {self.min_price:,} MAD"

        # 4. Mots-clés exclus
        for kw in self.exclude_keywords:
            if kw in text:
                return False, f"Mot-clé exclu trouvé: '{kw}'"

        # 5. Score minimum (si scoré)
        if listing.total_score is not None and listing.total_score < self.min_score:
            return False, f"Score {listing.total_score}/100 < minimum {self.min_score}"

        return True, ""

    def filter_all(self, listings: list[Listing]) -> list[Listing]:
        kept = []
        for listing in listings:
            ok, reason = self.passes(listing)
            if ok:
                kept.append(listing)
            else:
                logger.debug(f"Rejeté [{listing.source}] '{listing.title}': {reason}")

        logger.info(
            f"Filtrage: {len(kept)}/{len(listings)} annonces retenues."
        )
        return kept
