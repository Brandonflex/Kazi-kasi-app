"""Distance, cheaply and honestly.

The research is blunt about why this matters: job utility decays roughly
exponentially with distance (~0.3 per km; a role 5 km further out is about 4.5×
less attractive), and administrative boundaries are a bad proxy for a labour
market. A Nairobi-metro beta is a commute market, so a card has to answer "can
I get there?" and not just "which county is it in?".

What this module is **not**: a routing engine. It uses straight-line distance
between approximate area centroids. That is enough to rank and to band
("walkable", "one matatu", "far"), and it is wrong by a couple of kilometres in
places — so it is labelled ``approximate`` everywhere it surfaces, and it never
decides whether a job is *shown* unless the user set a distance cap.

The matatu GTFS in the research pack is the upgrade path: same interface, real
travel times instead of straight lines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Coordinates are approximate centroids, rounded to 3 dp (~100 m) purely to
#: avoid false precision. Source: public gazetteer values; verified by eye
#: against a map, not surveyed.
NAIROBI_AREAS: dict[str, tuple[float, float]] = {
    "cbd": (-1.2841, 36.8219),
    "starehe": (-1.2841, 36.8219),
    "city centre": (-1.2841, 36.8219),
    "upper hill": (-1.2985, 36.8155),
    "south b": (-1.2960, 36.8240),
    "south c": (-1.3120, 36.8000),
    "westlands": (-1.2673, 36.8065),
    "parklands": (-1.2600, 36.8200),
    "gigiri": (-1.2300, 36.8000),
    "highridge": (-1.2650, 36.8150),
    "kilimani": (-1.2916, 36.7860),
    "kileleshwa": (-1.2830, 36.7800),
    "lavington": (-1.2760, 36.7680),
    "dagoretti": (-1.2900, 36.7400),
    "ngong road": (-1.3000, 36.7700),
    "karen": (-1.3300, 36.7100),
    "langata": (-1.3667, 36.7500),
    "madaraka": (-1.3050, 36.8100),
    "industrial area": (-1.3090, 36.8450),
    "embakasi": (-1.3167, 36.9000),
    "mombasa road": (-1.3400, 36.8800),
    "kasarani": (-1.2333, 36.8833),
    "ruaraka": (-1.2400, 36.8700),
    "thika road": (-1.2200, 36.8900),
    "roysambu": (-1.2200, 36.8800),
    "kibra": (-1.3100, 36.7900),
    "makadara": (-1.3050, 36.8600),
    "kamukunji": (-1.2830, 36.8400),
    "mathare": (-1.2600, 36.8600),
}

#: County centroids for the wider market, used only for county-level distance.
COUNTY_CENTROIDS: dict[str, tuple[float, float]] = {
    "Nairobi": (-1.2921, 36.8219),
    "Kiambu": (-1.1714, 36.8356),
    "Machakos": (-1.5177, 37.2634),
    "Kajiado": (-1.8521, 36.7768),
    "Murang'a": (-0.7210, 37.1526),
    "Nyeri": (-0.4169, 36.9517),
    "Nakuru": (-0.3031, 36.0800),
    "Mombasa": (-4.0435, 39.6682),
    "Kisumu": (-0.0917, 34.7680),
    "Uasin Gishu": (0.5143, 35.2698),
    "Kisii": (-0.6817, 34.7667),
    "Kakamega": (0.2827, 34.7519),
}

METRO_COUNTIES = ("Nairobi", "Kiambu", "Machakos", "Kajiado")

#: Bands, not numbers, in front of a user. A straight-line km is not a journey.
BANDS = (
    (3.0, "walkable"),
    (8.0, "one matatu"),
    (16.0, "long commute"),
    (40.0, "across the metro"),
    (math.inf, "outside the metro"),
)


@dataclass(frozen=True)
class Distance:
    km: float
    band: str
    approximate: bool = True
    from_label: str | None = None
    to_label: str | None = None

    def to_dict(self) -> dict:
        return {
            "km": round(self.km, 1),
            "band": self.band,
            "approximate": self.approximate,
            "from": self.from_label,
            "to": self.to_label,
        }


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def band_for(km: float) -> str:
    for limit, label in BANDS:
        if km <= limit:
            return label
    return "outside the metro"


def _normalise(value: str | None) -> str:
    return (value or "").strip().lower().replace("  ", " ")


def coordinates_for(area: str | None, county: str | None) -> tuple[float, float] | None:
    """Area first, county second. ``None`` when we do not know the place."""
    if area:
        key = _normalise(area)
        if key in NAIROBI_AREAS:
            return NAIROBI_AREAS[key]
    if county:
        for name, coords in COUNTY_CENTROIDS.items():
            if _normalise(name) == _normalise(county):
                return coords
    return None


def distance_between(
    from_area: str | None,
    from_county: str | None,
    to_area: str | None,
    to_county: str | None,
) -> Distance | None:
    """Approximate distance between two places, or ``None`` if either is unknown.

    ``None`` is a real answer and callers must handle it: a posting with no
    location is not nearby, it is *unknown*, and pretending otherwise is how a
    feed starts lying about reachability.
    """
    start = coordinates_for(from_area, from_county)
    end = coordinates_for(to_area, to_county)
    if start is None or end is None:
        return None
    km = haversine_km(start, end)
    return Distance(
        km=round(km, 2),
        band=band_for(km),
        from_label=from_area or from_county,
        to_label=to_area or to_county,
    )


def commute_utility(km: float | None, decay: float = 0.3) -> float:
    """0–1 utility from distance, decaying exponentially.

    ``exp(-0.3 * km)`` is the research's approximation: at 5 km a role keeps
    about 22% of its proximity value, which matches the "4.5× less attractive"
    finding without pretending to be a model of Nairobi traffic.
    """
    if km is None:
        return 0.5  # unknown, not zero: we do not punish a missing field
    return math.exp(-decay * max(0.0, km))


def in_metro(county: str | None) -> bool:
    return bool(county) and _normalise(county) in {_normalise(c) for c in METRO_COUNTIES}
