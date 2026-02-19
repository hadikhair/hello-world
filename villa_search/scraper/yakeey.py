"""
Scraper pour Yakeey.com - villas Marrakech.
URL pattern: https://yakeey.com/fr-ma/immobilier-marrakech/villa-a-vendre
"""

import logging
from typing import Iterator
from urllib.parse import urljoin

from villa_search.models import Listing
from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://yakeey.com"
SEARCH_URL = (
    "https://yakeey.com/fr-ma/immobilier-marrakech/villa-a-vendre"
    "?page={page}"
)


class YakeeyScaper(BaseScraper):
    source_name = "yakeey"

    def search_pages(self) -> Iterator[Listing]:
        page = 1
        while True:
            url = SEARCH_URL.format(page=page)
            logger.info(f"[Yakeey] Page {page}: {url}")
            try:
                resp = self.polite_get(url)
            except Exception:
                break

            soup = self.parse_html(resp.text)
            cards = soup.select(".property-card, .listing-card, [data-cy='property']")

            if not cards:
                logger.info(f"[Yakeey] Aucune annonce page {page}, arrêt.")
                break

            for card in cards:
                listing = self._parse_card(card)
                if listing:
                    yield listing

            next_btn = soup.select_one("a[rel='next'], .pagination .next")
            if not next_btn:
                break
            page += 1

    def _parse_card(self, card) -> Listing | None:
        try:
            link_el = card.select_one("a[href]")
            url = urljoin(BASE_URL, link_el["href"]) if link_el else ""

            title_el = card.select_one("h2, .property-title, .card-title")
            title = title_el.get_text(strip=True) if title_el else ""

            price_el = card.select_one(".price, .property-price, [data-price]")
            price = self.parse_price(price_el.get_text()) if price_el else None

            surface_el = card.select_one(".surface, [data-surface]")
            surface = self.parse_int(surface_el.get_text()) if surface_el else None

            rooms_el = card.select_one(".rooms, .bedrooms, [data-rooms]")
            bedrooms = self.parse_int(rooms_el.get_text()) if rooms_el else None

            location_el = card.select_one(".location, .neighborhood, .address")
            neighborhood = location_el.get_text(strip=True) if location_el else ""

            img_el = card.select_one("img[src], img[data-src]")
            img_src = (img_el.get("data-src") or img_el.get("src")) if img_el else None
            images = [img_src] if img_src else []

            if not url:
                return None

            detail = self._fetch_detail(url)

            fp = self.make_fingerprint(url, title, str(price))
            return Listing(
                id=fp,
                source=self.source_name,
                url=url,
                title=title,
                price_mad=price,
                surface_m2=detail.get("surface") or surface,
                bedrooms=detail.get("bedrooms") or bedrooms,
                bathrooms=detail.get("bathrooms"),
                neighborhood=neighborhood,
                description=detail.get("description", ""),
                images=detail.get("images") or images,
            )
        except Exception as e:
            logger.warning(f"[Yakeey] Erreur parsing card: {e}")
            return None

    def _fetch_detail(self, url: str) -> dict:
        result = {}
        try:
            resp = self.polite_get(url)
            soup = self.parse_html(resp.text)

            desc_el = soup.select_one(".description, .property-description")
            result["description"] = desc_el.get_text(strip=True) if desc_el else ""

            for feat in soup.select(".feature-item, .criteria li, .amenity"):
                text = feat.get_text(strip=True).lower()
                if "m²" in text:
                    result["surface"] = self.parse_int(text)
                elif "chambre" in text:
                    result["bedrooms"] = self.parse_int(text)
                elif "bain" in text:
                    result["bathrooms"] = self.parse_int(text)

            imgs = [
                img.get("data-src") or img.get("src")
                for img in soup.select(".gallery img, .slider-image")
            ]
            result["images"] = [i for i in imgs if i][:8]

        except Exception as e:
            logger.debug(f"[Yakeey] Impossible fetch détail {url}: {e}")
        return result
