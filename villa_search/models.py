from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Listing:
    id: str                          # fingerprint unique
    source: str                      # avito / mubawab / yakeey
    url: str
    title: str
    price_mad: Optional[int]
    surface_m2: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    neighborhood: Optional[str]
    description: str
    images: list[str] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.now)
    is_new: bool = True

    # Scores (remplis par le scorer)
    price_score: Optional[float] = None      # 0-100, 100 = très bon prix
    surface_score: Optional[float] = None
    location_score: Optional[float] = None
    style_score: Optional[float] = None
    total_score: Optional[float] = None
    score_label: Optional[str] = None        # "Excellent", "Bon", "Moyen", "Cher"
    price_vs_market: Optional[float] = None  # -15% = 15% sous le marché

    @property
    def price_per_m2(self) -> Optional[float]:
        if self.price_mad and self.surface_m2 and self.surface_m2 > 0:
            return self.price_mad / self.surface_m2
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "price_mad": self.price_mad,
            "surface_m2": self.surface_m2,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "neighborhood": self.neighborhood,
            "description": self.description,
            "images": self.images,
            "scraped_at": self.scraped_at.isoformat(),
            "is_new": self.is_new,
            "price_score": self.price_score,
            "surface_score": self.surface_score,
            "location_score": self.location_score,
            "style_score": self.style_score,
            "total_score": self.total_score,
            "score_label": self.score_label,
            "price_vs_market": self.price_vs_market,
            "price_per_m2": self.price_per_m2,
        }
