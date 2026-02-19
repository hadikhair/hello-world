"""
Scraper pour Avito.ma - section immobilier villas Marrakech.
URL pattern: https://www.avito.ma/fr/marrakech/villas-à_vendre
"""

import logging
from typing import Iterator
from urllib.parse import urljoin

from villa_search.models import Listing
from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.avito.ma"
SEARCH_URL = (
    "https://www.avito.ma/fr/marrakech/villas-à_vendre"
    "?o={page}"
)


class AvitoScraper(BaseScraper):
    source_name = "avito"

    def search_pages(self) -> Iterator[Listing]:
        page = 1
        while True:
            url = SEARCH_URL.format(page=page)
            logger.info(f"[Avito] Page {page}: {url}")
            try:
                resp = self.polite_get(url)
            except Exception:
                break

            soup = self.parse_html(resp.text)
            listings = soup.select("article.sc-1nre5ec-1")

            if not listings:
                # Essayer un sélecteur alternatif (Avito change parfois son HTML)
                listings = soup.select("[data-cy='adListingCard']")

            if not listings:
                logger.info(f"[Avito] Aucune annonce page {page}, arrêt.")
                break

            for card in listings:
                listing = self._parse_card(card)
                if listing:
                    yield listing

            # Pagination : vérifier s'il y a une page suivante
            next_btn = soup.select_one("a[data-cy='next-page']") or \
                       soup.select_one(".pagination-next a")
            if not next_btn:
                break
            page += 1

    def _parse_card(self, card) -> Listing | None:
        try:
            # Titre
            title_el = card.select_one("p.sc-1x0vz2r-0") or \
                       card.select_one("[data-cy='title']") or \
                       card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            # URL
            link_el = card.select_one("a[href]")
            url = urljoin(BASE_URL, link_el["href"]) if link_el else ""

            # Prix
            price_el = card.select_one("p.sc-1nre5ec-13") or \
                       card.select_one("[data-cy='price']") or \
                       card.select_one(".price")
            price = self.parse_price(price_el.get_text()) if price_el else None

            # Surface & chambres depuis le sous-titre
            desc_el = card.select_one("p.sc-1nre5ec-14") or \
                      card.select_one("[data-cy='description']")
            desc_text = desc_el.get_text(strip=True) if desc_el else ""

            surface = self._extract_surface(desc_text)
            bedrooms = self._extract_bedrooms(desc_text)

            # Localisation
            location_el = card.select_one("[data-cy='location']") or \
                          card.select_one(".sc-1nre5ec-15")
            neighborhood = location_el.get_text(strip=True) if location_el else ""

            # Images
            img_el = card.select_one("img[src]")
            images = [img_el["src"]] if img_el else []

            if not url:
                return None

            # On fetch la page de détail pour la description complète
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
                description=detail.get("description") or desc_text,
                images=detail.get("images") or images,
            )
        except Exception as e:
            logger.warning(f"[Avito] Erreur parsing card: {e}")
            return None

    def _fetch_detail(self, url: str) -> dict:
        """Récupère les infos détaillées depuis la page annonce."""
        import re
        result = {}
        try:
            resp = self.polite_get(url)
            soup = self.parse_html(resp.text)

            # Description
            desc_el = soup.select_one("[data-cy='ad-description']") or \
                      soup.select_one(".sc-1g3sn3w-14")
            result["description"] = desc_el.get_text(strip=True) if desc_el else ""

            # Caractéristiques (surface, chambres...)
            for item in soup.select("li.sc-qmn92k-0, [data-cy='ad-criteria-item']"):
                text = item.get_text(strip=True).lower()
                if "m²" in text or "superficie" in text:
                    result["surface"] = self.parse_int(text)
                elif "chambre" in text:
                    result["bedrooms"] = self.parse_int(text)
                elif "salle de bain" in text or "sdb" in text:
                    result["bathrooms"] = self.parse_int(text)

            # Images
            imgs = [img["src"] for img in soup.select("img.sc-1n3sl4h-5[src]")]
            result["images"] = imgs[:8]

        except Exception as e:
            logger.debug(f"[Avito] Impossible fetch détail {url}: {e}")
        return result

    @staticmethod
    def _extract_surface(text: str) -> int | None:
        import re
        m = re.search(r"(\d[\d\s]*)\s*m²", text, re.IGNORECASE)
        return int(re.sub(r"\s", "", m.group(1))) if m else None

    @staticmethod
    def _extract_bedrooms(text: str) -> int | None:
        import re
        m = re.search(r"(\d+)\s*chambre", text, re.IGNORECASE)
        return int(m.group(1)) if m else None
