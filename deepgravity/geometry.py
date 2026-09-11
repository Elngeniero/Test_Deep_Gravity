"""Coordinate contract: model anchors are [latitude, longitude], degrees; km."""
from math import asin, cos, isfinite, pi, sin, sqrt


def earth_distance(lat_lng1, lat_lng2):
    for latitude, longitude in (lat_lng1, lat_lng2):
        if not (isfinite(latitude) and isfinite(longitude) and
                -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Expected [latitude, longitude] in WGS84 degrees")
    lat1, lng1 = [value * pi / 180 for value in lat_lng1]
    lat2, lng2 = [value * pi / 180 for value in lat_lng2]
    a = sin((lat1 - lat2) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng1 - lng2) / 2) ** 2
    return 6371.01 * 2 * asin(sqrt(min(1.0, max(0.0, a))))
