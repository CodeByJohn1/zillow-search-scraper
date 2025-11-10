import math
from typing import Tuple

def haversine_distance_km(
lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
"""
Compute the great-circle distance between two coordinates using the Haversine formula.

All coordinates are in decimal degrees. Result is in kilometers.
"""
    # Earth radius in kilometers
radius_earth_km = 6371.0

    # Convert degrees to radians
lat1_rad = math.radians(lat1)
lon1_rad = math.radians(lon1)
lat2_rad = math.radians(lat2)
lon2_rad = math.radians(lon2)

dlat = lat2_rad - lat1_rad
dlon = lon2_rad - lon1_rad

a = (
math.sin(dlat / 2) ** 2
+ math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
)
c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

return radius_earth_km * c

def bounding_box_from_center(
lat: float, lon: float, radius_km: float
) -> Tuple[float, float, float, float]:
"""
Roughly compute a latitude/longitude bounding box around a center point.

Returns (min_lat, min_lon, max_lat, max_lon).
"""
    # Approximate conversions