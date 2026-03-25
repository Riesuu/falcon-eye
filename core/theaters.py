# -*- coding: utf-8 -*-
"""
Falcon-Eye — core/theaters.py
Theater projection parameters and coordinate conversion.

Every BMS theater uses a custom Transverse Mercator projection.
This module stores per-theater parameters and converts BMS coordinates
(North ft, East ft) to WGS-84 (lat, lon).

Ported from Falcon-Pad theaters.py — Riesu — GNU GPL v3
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# ── WGS-84 constants ─────────────────────────────────────────────────────────
_A   = 6378137.0           # semi-major axis (m)
_E2  = 0.00669437999014    # first eccentricity squared
_FTM = 0.3048              # feet → metres


# ── Theater descriptor ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TheaterParams:
    """TMERC projection parameters for a single BMS theater."""
    name: str
    lon0: float   # central meridian (degrees)
    k0:   float   # scale factor
    FE:   float   # false easting  (metres)
    FN:   float   # false northing (metres)
    bbox: Tuple[float, float, float, float]  # (lat_min, lat_max, lon_min, lon_max)


# ── Registry ──────────────────────────────────────────────────────────────────
THEATER_DB: Dict[str, TheaterParams] = {}


def _reg(name: str, lon0: float, k0: float, FE: float, FN: float,
         bbox: Tuple[float, float, float, float]) -> None:
    THEATER_DB[name.lower()] = TheaterParams(name, lon0, k0, FE, FN, bbox)


# Sources: BMS terrain header files + community documentation
_reg("Korea",     lon0=127.5, k0=0.9996, FE=512000.0, FN=-3749290.0,
     bbox=(30.0, 45.0, 118.0, 135.0))
_reg("Korea KTO", lon0=127.5, k0=0.9996, FE=512000.0, FN=-3749290.0,
     bbox=(30.0, 45.0, 118.0, 135.0))
_reg("Balkans",   lon0=20.0,  k0=0.9996, FE=500000.0, FN=0.0,
     bbox=(35.0, 50.0, 12.0, 32.0))
_reg("Israel",    lon0=35.5,  k0=0.9996, FE=500000.0, FN=0.0,
     bbox=(27.0, 37.0, 29.0, 42.0))
_reg("Aegean",    lon0=24.0,  k0=0.9996, FE=500000.0, FN=0.0,
     bbox=(33.0, 43.0, 18.0, 32.0))
_reg("Iberia",    lon0=-4.0,  k0=0.9996, FE=500000.0, FN=0.0,
     bbox=(34.0, 45.0, -12.0, 5.0))
_reg("Nordic",    lon0=18.0,  k0=0.9996, FE=500000.0, FN=0.0,
     bbox=(54.0, 72.0, 4.0, 36.0))


# ── Active theater state ──────────────────────────────────────────────────────
_active: TheaterParams = THEATER_DB["korea"]
_active_name: str = "Korea"


def get_theater() -> TheaterParams:
    return _active


def get_theater_name() -> str:
    return _active_name


def set_active_theater(name: str) -> bool:
    """Set active theater from a name string (e.g. from StringData ThrName).
    Returns True if theater actually changed."""
    global _active, _active_name
    raw = name.strip()
    key = raw.lower()

    # Direct match
    if key in THEATER_DB:
        if _active_name.lower() != key:
            _active = THEATER_DB[key]
            _active_name = raw
            logger.info(f"Theater → {_active_name}  (lon0={_active.lon0}°, bbox={_active.bbox})")
            return True
        return False

    # Fuzzy substring match ("Korea 1.1" → "korea")
    for db_key, params in THEATER_DB.items():
        if db_key in key or key in db_key:
            if _active_name.lower() != db_key:
                _active = params
                _active_name = raw
                logger.info(f"Theater (fuzzy) '{raw}' → {db_key}")
                return True
            return False

    logger.warning(f"Theater unknown: '{raw}' — keeping {_active_name}")
    return False


# ── TMERC reverse projection ──────────────────────────────────────────────────
def _tmerc(north_ft: float, east_ft: float, tp: TheaterParams) -> Tuple[float, float]:
    """BMS (North ft, East ft) → WGS-84 (lat°, lon°) for a given theater."""
    lon0 = math.radians(tp.lon0)
    k0, FE, FN = tp.k0, tp.FE, tp.FN
    E_m = east_ft  * _FTM
    N_m = north_ft * _FTM

    e1  = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    M1  = (N_m - FN) / k0
    mu1 = M1 / (_A * (1 - _E2/4 - 3*_E2**2/64 - 5*_E2**3/256))

    phi1 = (mu1
            + (3*e1/2   - 27*e1**3/32) * math.sin(2*mu1)
            + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu1)
            + (151*e1**3/96)              * math.sin(6*mu1))

    sp1 = math.sin(phi1); cp1 = math.cos(phi1); tp1 = math.tan(phi1)
    N1r = _A / math.sqrt(1 - _E2*sp1**2)
    T1  = tp1**2
    C1  = _E2 * cp1**2 / (1 - _E2)
    R1  = _A * (1 - _E2) / (1 - _E2*sp1**2)**1.5
    D   = (E_m - FE) / (N1r * k0)

    lat = phi1 - (N1r*tp1/R1) * (D**2/2 - (5+3*T1+10*C1-4*C1**2-9*_E2)*D**4/24)
    lon = lon0 + (D - (1+2*T1+C1)*D**3/6) / cp1

    return math.degrees(lat), math.degrees(lon)


def bms_to_latlon(north_ft: float, east_ft: float) -> Tuple[float, float]:
    """Convert BMS coords using the *active* theater projection."""
    return _tmerc(north_ft, east_ft, _active)


def in_theater_bbox(lat: float, lon: float) -> bool:
    """True if (lat, lon) falls within the active theater bounding box."""
    bb = _active.bbox
    return bb[0] <= lat <= bb[1] and bb[2] <= lon <= bb[3]


def theater_center_zoom() -> Tuple[float, float, int]:
    """Return (center_lat, center_lon, zoom) for the active theater."""
    bb = _active.bbox
    c_lat = (bb[0] + bb[1]) / 2
    c_lon = (bb[2] + bb[3]) / 2
    span  = max(bb[1]-bb[0], bb[3]-bb[2])
    zoom  = 6 if span > 20 else 7 if span > 15 else 8
    return c_lat, c_lon, zoom
