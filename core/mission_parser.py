# -*- coding: utf-8 -*-
"""
Mission INI Parser v2 — lit les fichiers .ini BMS et en extrait:
  - Bullseye  : premier target_N non-nul (ou clé contenant 'bull')
  - Route     : target_N (waypoints)
  - Menaces   : ppt_N (SAM/AAA avec nom et rayon)
  - Lignes    : lineSTPT_N (FLOT / lignes de front)
  - Flightplan: wpntarget_N (plan de vol secondaire)

Format des entrées STPT :
  key = X, Y, Z[, radius, name]
  X/Y en pieds TMERC Korea (bms_to_latlon)
  Z en pieds (altitude, négatif = sol)
"""
import re
import logging
from core.data import bms_to_latlon
from core.theaters import in_theater_bbox

logger = logging.getLogger(__name__)


def _in_kto(lat, lon):
    """Vérifie si les coords sont dans le bbox du théâtre actif."""
    return in_theater_bbox(lat, lon)


def _parse_entry(val: str):
    """Parse 'X, Y, Z[, radius, name]' → (x,y,z,radius,name) ou None."""
    parts = [p.strip() for p in val.split(",")]
    if len(parts) < 3:
        return None
    try:
        x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None
    if x == 0.0 and y == 0.0:
        return None
    radius = 0.0
    name   = ""
    if len(parts) >= 4:
        try:    radius = float(parts[3])
        except (ValueError, TypeError): radius = 0.0
    if len(parts) >= 5:
        name = parts[4].strip()
    return x, y, z, radius, name


def parse_mission_ini(content: str) -> dict:
    route, threats, lines, fplan, ref_points = [], [], [], [], []
    bullseye = None

    # Normaliser fins de ligne
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Parser manuel (configparser échoue sur certains INI BMS sans sections)
    in_stpt = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line.lower() == "[stpt]":
            in_stpt = True
            continue
        if line.startswith("["):
            in_stpt = False
            continue
        if not in_stpt:
            continue
        if "=" not in line:
            continue

        key, _, val = line.partition("=")
        key = key.strip().lower()
        val = val.strip()

        parsed = _parse_entry(val)
        if parsed is None:
            continue
        x, y, z, radius, name = parsed

        lat, lon = bms_to_latlon(x, y)
        if not _in_kto(lat, lon):
            continue

        if "bull" in key:
            bullseye = {"lat": lat, "lon": lon}

        elif key.startswith("ppt_"):
            range_m  = int(radius * 0.3048)
            # Séparer vrais SAM (range > 500m) des points de nav (IP, repères)
            if range_m > 500:
                range_nm = max(1, round(radius / 6076.12))
                display = name if name and not name.isdigit() else f"SAM-{name}" if name else "SAM"
                threats.append({
                    "lat": lat, "lon": lon,
                    "name": display,
                    "range_nm": range_nm,
                    "range_m":  range_m,
                    "index": len(threats),
                })
            else:
                # Point de nav / IP / repère (pas d'anneau SAM)
                display = name if name else f"PPT{len(ref_points)}"
                ref_points.append({
                    "lat": lat, "lon": lon,
                    "name": display,
                    "index": len(ref_points),
                })

        elif key.startswith("linestpt_"):
            lines.append({"lat": lat, "lon": lon, "index": len(lines)})

        elif key.startswith("wpntarget_"):
            fplan.append({"lat": lat, "lon": lon, "alt": z, "index": len(fplan)})

        elif key.startswith("target_"):
            # Waypoints de route principale
            # Ignorer les index > 79 (targets spéciaux BMS)
            idx_str = key.replace("target_", "")
            try:    idx = int(idx_str)
            except (ValueError, TypeError): continue
            if idx > 79:
                continue
            route.append({"lat": lat, "lon": lon, "alt": z,
                          "name": name, "index": len(route)})

    # Bullseye par défaut = premier waypoint de route
    if bullseye is None and route:
        bullseye = {"lat": route[0]["lat"], "lon": route[0]["lon"]}
        logger.info("Bullseye déduit du premier waypoint route")

    # Grouper les lineSTPT en segments (coupés par les entrées 0,0,0 dans l'INI)
    line_segments = _group_line_segments(content)

    logger.info(
        f"INI parsé: bull={bullseye} route={len(route)} "
        f"threats={len(threats)} refs={len(ref_points)} lines={len(lines)} "
        f"segments={len(line_segments)} fplan={len(fplan)}"
    )
    return {
        "bullseye":      bullseye,
        "route":         route,
        "threats":       threats,
        "ref_points":    ref_points,
        "lines":         lines,
        "line_segments": line_segments,
        "flightplan":    fplan,
    }


def _group_line_segments(content: str) -> list:
    """
    Regroupe les lineSTPT en segments continus.
    Les entrées 0,0,0 dans l'INI original séparent les segments.
    On reconstitue en triant par index et en coupant aux trous.
    """
    entries = {}
    in_stpt = False
    for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if line.lower() == "[stpt]":  in_stpt = True;  continue
        if line.startswith("["):      in_stpt = False;  continue
        if not in_stpt or "=" not in line: continue
        key, _, val = line.partition("=")
        key = key.strip().lower()
        if not key.startswith("linestpt_"): continue
        idx_str = key.replace("linestpt_", "")
        try:    idx = int(idx_str)
        except (ValueError, TypeError): continue
        parts = [p.strip() for p in val.split(",")]
        try:    x, y = float(parts[0]), float(parts[1])
        except (ValueError, TypeError, IndexError): continue
        entries[idx] = (x, y)

    if not entries: return []

    segments, current = [], []
    for i in sorted(entries.keys()):
        x, y = entries[i]
        if x == 0.0 and y == 0.0:
            if len(current) >= 2:
                segments.append(current)
            current = []
        else:
            lat, lon = bms_to_latlon(x, y)
            if _in_kto(lat, lon):
                current.append({"lat": lat, "lon": lon})
    if len(current) >= 2:
        segments.append(current)
    return segments


def _empty() -> dict:
    return {"bullseye": None, "route": [], "threats": [], "ref_points": [],
            "lines": [], "line_segments": [], "flightplan": []}
