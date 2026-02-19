"""
Pipeline principal : scrape → filtre → dédoublonne → score → email.
"""

import logging
from typing import Optional

from villa_search.models import Listing
from villa_search.scraper import AvitoScraper, MubawabScraper, YakeeyScaper
from villa_search.filter import ListingFilter
from villa_search.dedup import DeduplicationStore
from villa_search.scorer import ListingScorer
from villa_search.mailer import send_daily_digest

logger = logging.getLogger(__name__)


def run_pipeline(config: dict, dry_run: bool = False) -> list[Listing]:
    """
    Lance le pipeline complet.

    Args:
        config: configuration chargée depuis config.yaml
        dry_run: si True, n'envoie pas l'email (utile pour tester)

    Returns:
        Liste des annonces retenues et scorées.
    """
    sources_cfg = config.get("sources", {})

    # ── 1. Scraping ──────────────────────────────────────────────────────────
    all_listings: list[Listing] = []

    scrapers = []
    if sources_cfg.get("avito", True):
        scrapers.append(AvitoScraper(config))
    if sources_cfg.get("mubawab", True):
        scrapers.append(MubawabScraper(config))
    if sources_cfg.get("yakeey", True):
        scrapers.append(YakeeyScaper(config))

    for scraper in scrapers:
        logger.info(f"Scraping source: {scraper.source_name}")
        try:
            for listing in scraper.search_pages():
                all_listings.append(listing)
        except Exception as e:
            logger.error(f"Erreur scraper {scraper.source_name}: {e}")

    logger.info(f"Total brut: {len(all_listings)} annonces récupérées.")

    # ── 2. Filtrage métier (avant dédup pour économiser les requêtes) ─────────
    listing_filter = ListingFilter(config, min_score=0)  # score pas encore calculé
    filtered = listing_filter.filter_all(all_listings)

    # ── 3. Déduplication ─────────────────────────────────────────────────────
    dedup = DeduplicationStore()
    new_listings = dedup.filter_new(filtered)

    # ── 4. Scoring ───────────────────────────────────────────────────────────
    scorer = ListingScorer(config)
    scored = scorer.score_all(new_listings)

    # ── 5. Filtre post-score (éliminer les annonces trop mauvaises) ───────────
    min_score = config.get("scoring", {}).get("min_score_to_send", 35.0)
    final = [l for l in scored if (l.total_score or 0) >= min_score]

    logger.info(
        f"Pipeline terminé: {len(final)} annonces retenues sur "
        f"{len(all_listings)} brutes."
    )

    # ── 6. Email digest ──────────────────────────────────────────────────────
    if not dry_run:
        if final:
            send_daily_digest(final, config)
        else:
            logger.info("Aucune annonce à envoyer aujourd'hui.")
    else:
        logger.info(f"[DRY RUN] {len(final)} annonces prêtes (email non envoyé).")

    return final
