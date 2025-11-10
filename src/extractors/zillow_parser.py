from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

from .utils_geo import haversine_distance_km

LOGGER = logging.getLogger("zillow_scraper.parser")

def _parse_int_from_price(value: Any) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    # Remove currency signs and separators
    for ch in ("$", ",", " "):
        cleaned = cleaned.replace(ch, "")

    # Handle things like "995K", "1.2M"
    multiplier = 1
    if cleaned.endswith(("k", "K", "m", "M")):
        unit = cleaned[-1].lower()
        cleaned = cleaned[:-1]
        if unit == "k":
            multiplier = 1_000
        elif unit == "m":
            multiplier = 1_000_000

    try:
        if "." in cleaned:
            return int(float(cleaned) * multiplier)
        return int(cleaned) * multiplier
    except (ValueError, TypeError):
        LOGGER.debug("Could not parse int from price %r", value)
        return None

def _get_nested(data: Dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

@dataclass
class ZillowListing:
    zpid: str
    price: Optional[int]
    address: Optional[str]
    home_type: Optional[str]
    zestimate: Optional[int]
    rent_zestimate: Optional[int]
    beds: Optional[int]
    baths: Optional[float]
    area: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    broker_name: Optional[str]
    photos: List[str]
    detail_url: Optional[str]
    date_posted: Optional[str]
    status_text: Optional[str]

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "ZillowListing":
        """
        Create a ZillowListing from a raw listing dict, trying to be resilient
        to small structure differences.
        """
        zpid = str(raw.get("zpid") or raw.get("id") or "")

        if not zpid:
            raise ValueError("Listing is missing 'zpid' or 'id' field")

        # Prices
        raw_price = raw.get("price") or raw.get("unformattedPrice")
        price = _parse_int_from_price(raw_price)

        zestimate = _parse_int_from_price(
            raw.get("zestimate") or _get_nested(raw, "hdpData", "homeInfo", "zestimate")
        )

        rent_zestimate = _parse_int_from_price(
            raw.get("rentZestimate")
            or _get_nested(raw, "hdpData", "homeInfo", "rentZestimate")
        )

        address = raw.get("address") or _get_nested(
            raw, "hdpData", "homeInfo", "formattedAddress"
        )

        home_type = raw.get("homeType") or _get_nested(
            raw, "hdpData", "homeInfo", "homeType"
        )

        beds = raw.get("beds") or _get_nested(raw, "hdpData", "homeInfo", "bedrooms")
        if isinstance(beds, str):
            try:
                beds = int(beds)
            except ValueError:
                beds = None

        baths = raw.get("baths") or _get_nested(
            raw, "hdpData", "homeInfo", "bathrooms"
        )
        if isinstance(baths, str):
            try:
                baths = float(baths)
            except ValueError:
                baths = None

        area = raw.get("area") or _get_nested(
            raw, "hdpData", "homeInfo", "livingArea"
        )
        if isinstance(area, str):
            cleaned = area.replace(",", "").strip()
            try:
                area = int(float(cleaned))
            except ValueError:
                area = None

        lat_long = raw.get("latLong") or {
            "latitude": _get_nested(raw, "hdpData", "homeInfo", "latitude"),
            "longitude": _get_nested(raw, "hdpData", "homeInfo", "longitude"),
        }
        latitude = None
        longitude = None
        if isinstance(lat_long, dict):
            try:
                latitude = (
                    float(lat_long.get("latitude"))
                    if lat_long.get("latitude") is not None
                    else None
                )
                longitude = (
                    float(lat_long.get("longitude"))
                    if lat_long.get("longitude") is not None
                    else None
                )
            except (TypeError, ValueError):
                latitude = None
                longitude = None

        broker_name = raw.get("brokerName") or raw.get("brokerNameText")

        # Photos
        photos_field = raw.get("photos") or raw.get("photoUrls")
        photos: List[str] = []
        if isinstance(photos_field, list):
            for p in photos_field:
                if isinstance(p, str):
                    photos.append(p)
                elif isinstance(p, dict):
                    url = p.get("url") or p.get("src")
                    if isinstance(url, str):
                        photos.append(url)

        img_src = raw.get("imgSrc")
        if isinstance(img_src, str) and img_src not in photos:
            photos.insert(0, img_src)

        detail_url = raw.get("detailUrl") or raw.get("detailUrlPath")
        status_text = raw.get("statusText") or raw.get("statusType")
        date_posted = raw.get("datePosted") or raw.get("timeOnZillow")

        return cls(
            zpid=zpid,
            price=price,
            address=address,
            home_type=home_type,
            zestimate=zestimate,
            rent_zestimate=rent_zestimate,
            beds=beds if isinstance(beds, int) else None,
            baths=float(baths) if baths is not None else None,
            area=int(area) if isinstance(area, (int, float)) else None,
            latitude=latitude,
            longitude=longitude,
            broker_name=broker_name,
            photos=photos,
            detail_url=detail_url,
            date_posted=str(date_posted) if date_posted is not None else None,
            status_text=status_text,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def parse_zillow_search_results(
    raw_listings: Iterable[Dict[str, Any]],
) -> List[ZillowListing]:
    """
    Convert an iterable of raw listing dicts into structured ZillowListing objects.
    Listings that cannot be parsed are logged and skipped.
    """
    listings: List[ZillowListing] = []
    skipped = 0
    for raw in raw_listings:
        if not isinstance(raw, dict):
            LOGGER.debug("Skipping non-dict listing %r", raw)
            skipped += 1
            continue
        try:
            listing = ZillowListing.from_raw(raw)
            listings.append(listing)
        except Exception as exc:
            LOGGER.warning("Skipping listing due to parse error: %s", exc)
            skipped += 1

    LOGGER.info("Parsed %d listings (%d skipped)", len(listings), skipped)
    return listings

def filter_listings_by_radius(
    listings: Iterable[ZillowListing],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> List[ZillowListing]:
    """
    Filter listings that fall within a radius (in kilometers) of a given point.
    Listings without coordinates are excluded.
    """
    result: List[ZillowListing] = []
    for listing in listings:
        if listing.latitude is None or listing.longitude is None:
            continue
        distance = haversine_distance_km(
            center_lat, center_lon, listing.latitude, listing.longitude
        )
        if distance <= radius_km:
            result.append(listing)
    LOGGER.info(
        "Filtered %d listings within %.2f km of (%.4f, %.4f)",
        len(result),
        radius_km,
        center_lat,
        center_lon,
    )
    return result