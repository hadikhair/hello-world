"""
Moteur de scoring des annonces.

Score total /100 :
  - Prix (40 pts)    : comparé au prix médian du marché à Targa
  - Surface (25 pts) : rapport surface/prix et surface brute
  - Localisation (20 pts) : proximité Targa, quartiers premium
  - Style (15 pts)   : mots-clés modernes dans titre + description

Label final :
  >= 75  → Excellent deal
  55-74  → Bon rapport qualité/prix
  35-54  → Prix marché
  < 35   → Surévalué
"""

import logging
import re

from villa_search.models import Listing

logger = logging.getLogger(__name__)

# Quartiers classés par préférence (score localisation)
LOCATION_SCORES = {
    "targa": 100,
    "amelkis": 85,
    "agdal": 80,
    "guéliz": 75,
    "gueliz": 75,
    "hivernage": 80,
    "palmeraie": 70,
    "semlalia": 65,
    "massira": 55,
    "annakhil": 60,
}

MODERN_KEYWORDS = [
    "moderne", "contemporain", "neuf", "standing", "design",
    "haut standing", "récent", "recent", "construction récente",
    "architecture moderne", "villa moderne", "finition", "haut de gamme",
    "lumineux", "terrasse", "piscine", "climatisation", "parking",
]

NEGATIVE_KEYWORDS = [
    "traditionnel", "riad", "à rénover", "ruine", "travaux",
    "restaurer", "ancien", "vieille", "rénovation nécessaire",
]


class ListingScorer:
    def __init__(self, config: dict):
        self.cfg = config
        self.weights = config.get("scoring", {})
        self.market_price_m2 = self.weights.get("market_price_per_m2", 12000)

        self.w_price = self.weights.get("price_weight", 40)
        self.w_surface = self.weights.get("surface_weight", 25)
        self.w_location = self.weights.get("location_weight", 20)
        self.w_style = self.weights.get("style_weight", 15)

    def score(self, listing: Listing) -> Listing:
        listing.price_score = self._score_price(listing)
        listing.surface_score = self._score_surface(listing)
        listing.location_score = self._score_location(listing)
        listing.style_score = self._score_style(listing)

        total = (
            listing.price_score * self.w_price / 100
            + listing.surface_score * self.w_surface / 100
            + listing.location_score * self.w_location / 100
            + listing.style_score * self.w_style / 100
        )
        listing.total_score = round(min(100, max(0, total)), 1)
        listing.score_label = self._label(listing.total_score)

        if listing.price_per_m2 and self.market_price_m2:
            delta = (self.market_price_m2 - listing.price_per_m2) / self.market_price_m2
            listing.price_vs_market = round(delta * 100, 1)

        logger.debug(
            f"Score {listing.id}: total={listing.total_score} "
            f"prix={listing.price_score:.1f} surface={listing.surface_score:.1f} "
            f"loc={listing.location_score:.1f} style={listing.style_score:.1f}"
        )
        return listing

    def score_all(self, listings: list[Listing]) -> list[Listing]:
        scored = [self.score(l) for l in listings]
        # Tri par score décroissant
        scored.sort(key=lambda x: x.total_score or 0, reverse=True)
        return scored

    # ── Prix ────────────────────────────────────────────────────────────────

    def _score_price(self, listing: Listing) -> float:
        """
        Basé sur le prix au m² vs prix médian marché.
        Si pas de surface, on utilise le prix brut vs moyenne brute estimée.
        """
        if listing.price_per_m2:
            ratio = listing.price_per_m2 / self.market_price_m2
            # ratio < 1 = moins cher que le marché = bon
            if ratio <= 0.70:
                return 100.0   # -30% ou plus sous le marché
            elif ratio <= 0.85:
                return 85.0
            elif ratio <= 0.95:
                return 70.0
            elif ratio <= 1.05:
                return 55.0    # prix marché
            elif ratio <= 1.20:
                return 35.0
            elif ratio <= 1.40:
                return 15.0
            else:
                return 0.0     # très surévalué
        elif listing.price_mad:
            # Pas de surface connue : scoring simplifié sur prix brut
            cfg_search = self.cfg.get("search", {})
            mid = (
                cfg_search.get("min_price_mad", 2_000_000)
                + cfg_search.get("max_price_mad", 8_000_000)
            ) / 2
            ratio = listing.price_mad / mid
            return max(0, min(100, (2 - ratio) * 50))
        return 50.0  # prix inconnu → score neutre

    # ── Surface ─────────────────────────────────────────────────────────────

    def _score_surface(self, listing: Listing) -> float:
        if not listing.surface_m2:
            return 50.0  # inconnu → neutre
        s = listing.surface_m2
        if s >= 500:
            return 100.0
        elif s >= 400:
            return 90.0
        elif s >= 300:
            return 75.0
        elif s >= 250:
            return 60.0
        elif s >= 200:
            return 45.0
        elif s >= 150:
            return 25.0
        else:
            return 10.0

    # ── Localisation ────────────────────────────────────────────────────────

    def _score_location(self, listing: Listing) -> float:
        text = (listing.neighborhood or "" + " " + listing.title + " " + listing.description).lower()
        best = 0
        for keyword, score in LOCATION_SCORES.items():
            if keyword in text:
                best = max(best, score)
        return float(best) if best > 0 else 40.0  # quartier inconnu → score moyen-bas

    # ── Style moderne ────────────────────────────────────────────────────────

    def _score_style(self, listing: Listing) -> float:
        text = (listing.title + " " + listing.description).lower()

        # Pénalité pour mots négatifs
        for neg in NEGATIVE_KEYWORDS:
            if neg in text:
                return 0.0

        hits = sum(1 for kw in MODERN_KEYWORDS if kw in text)
        if hits == 0:
            return 30.0   # neutre, pas d'info
        elif hits == 1:
            return 50.0
        elif hits <= 3:
            return 70.0
        elif hits <= 5:
            return 85.0
        else:
            return 100.0

    # ── Label ────────────────────────────────────────────────────────────────

    @staticmethod
    def _label(score: float) -> str:
        if score >= 75:
            return "Excellent deal"
        elif score >= 55:
            return "Bon rapport qualite/prix"
        elif score >= 35:
            return "Prix marche"
        else:
            return "Surevalue"
