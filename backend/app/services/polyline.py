import math
from typing import List, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two points on Earth in meters
    using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def decode_polyline(encoded: str, precision: int = 5) -> List[Tuple[float, float]]:
    """
    Decodes a Google encoded polyline string into a list of (latitude, longitude) tuples.
    Pure-Python implementation with zero external C dependencies.
    """
    if not encoded:
        return []

    coordinates: List[Tuple[float, float]] = []
    index = 0
    length = len(encoded)
    lat = 0
    lng = 0

    while index < length:
        # Decode delta latitude
        shift = 0
        result = 0
        while index < length:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode delta longitude
        shift = 0
        result = 0
        while index < length:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        factor = 10 ** precision
        coordinates.append((lat / factor, lng / factor))

    return coordinates


def sample_polyline_coordinates(
    coords: List[Tuple[float, float]],
    max_samples: int = 8,
) -> List[Tuple[float, float]]:
    """
    Extracts representative sample coordinates evenly distributed along the route,
    always including the starting point and ending point.
    """
    if not coords or max_samples < 1:
        return []
    if len(coords) <= max_samples or max_samples <= 2:
        if max_samples == 1:
            return [coords[0]]
        if max_samples == 2 and len(coords) >= 2:
            return [coords[0], coords[-1]]
        return coords

    # Compute cumulative distances
    distances = [0.0]
    total_dist = 0.0
    for i in range(1, len(coords)):
        d = haversine_distance(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
        total_dist += d
        distances.append(total_dist)

    if total_dist == 0.0:
        return [coords[0]]

    # Sample uniformly spaced along distance
    sampled: List[Tuple[float, float]] = [coords[0]]
    step = total_dist / (max_samples - 1)

    curr_target = step
    coord_idx = 1

    while curr_target < total_dist - 1e-4 and len(sampled) < max_samples - 1:
        while coord_idx < len(distances) and distances[coord_idx] < curr_target:
            coord_idx += 1

        if coord_idx >= len(distances):
            break

        sampled.append(coords[coord_idx])
        curr_target += step

    # Ensure destination is always included as the final sample
    if coords[-1] not in sampled:
        sampled.append(coords[-1])

    return sampled
