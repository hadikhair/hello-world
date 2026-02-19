"""
Scraper pour Mubawab.ma - villas Marrakech.
URL pattern: https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-vendre:t:villa
"""

import logging
from typing import Iterator
from urllib.parse import urljoin

from villa_search.models import Listing
from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mubawab.ma"
SEARCH_URL = (
    "https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-vendre"
    ":t:villa:sc:targa,guéliz,annakhil:p:{page}"
)


class MubawabScraper(BaseScraper):
    source_name = "mubawab"

    def search_pages(self) -> Iterator[Listing]:
        page = 1
        while True:
            url = SEARCH_URL.format(page=page)
            logger.info(f"[Mubawab] Page {page}: {url}")
            try:
                resp = self.polite_get(url)
            except Exception:
                break

            soup = self.parse_html(resp.text)
            cards = soup.select("li.listingBox") or soup.select(".property-card")

            if not cards:
                logger.info(f"[Mubawab] Aucune annonce page {page}, arrêt.")
                break

            for card in cards:
                listing = self._parse_card(card)
                if listing:
                    yield listing

            next_btn = soup.select_one("a.nextPage") or \
                       soup.select_one("[rel='next']")
            if not next_btn:
                break
            page += 1

    def _parse_card(self, card) -> Listing | None:
        try:
            link_el = card.select_one("a[href]")
            url = urljoin(BASE_URL, link_el["href"]) if link_el else ""

            title_el = card.select_one("h2.listingTit") or card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            price_el = card.select_one("span.priceTag") or \
                       card.select_one(".price-block")
            price = self.parse_price(price_el.get_text()) if price_el else None

            size_el = card.select_one("span.listingSize")
            surface = self.parse_int(size_el.get_text()) if size_el else None

            rooms_el = card.select_one("span.listingRooms")
            bedrooms = self.parse_int(rooms_el.get_text()) if rooms_el else None

            location_el = card.select_one("span.listingH3") or \
                          card.select_one(".location-text")
            neighborhood = location_el.get_text(strip=True) if location_el else ""

            img_el = card.select_one("img[src]")
            images = [img_el["src"]] if img_el else []

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
            logger.warning(f"[Mubawab] Erreur parsing card: {e}")
            return None

    def _fetch_detail(self, url: str) -> dict:
        result = {}
        try:
            resp = self.polite_get(url)
            soup = self.parse_html(resp.text)

            desc_el = soup.select_one("div.propDesc") or \
                      soup.select_one(".description-block")
            result["description"] = desc_el.get_text(strip=True) if desc_el else ""

            for row in soup.select("ul.moreThan li, .property-features li"):
                text = row.get_text(strip=True).lower()
                if "m²" in text or "superficie" in text:
                    result["surface"] = self.parse_int(text)
                elif "chambre" in text:
                    result["bedrooms"] = self.parse_int(text)
                elif "bain" in text or "sdb" in text:
                    result["bathrooms"] = self.parse_int(text)

            imgs = [
                img.get("data-src") or img.get("src")
                for img in soup.select(".propGallery img, .slider img")
            ]
            result["images"] = [i for i in imgs if i][:8]

        except Exception as e:
            logger.debug(f"[Mubawab] Impossible fetch détail {url}: {e}")
        return result
