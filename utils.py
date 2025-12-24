"""
Planetastic: Utilities
Version: 2.1.0
Author: James Rich <james.a.rich@gmail.com>
"""
import math
import logging

logger = logging.getLogger(__name__)

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on the Earth (Haversine formula).
    Returns distance in kilometers.
    """
    R = 6371.0 # Radius of the Earth in km

    try:
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating distance: {e}")
        return float('inf')
