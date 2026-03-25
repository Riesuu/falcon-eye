# -*- coding: utf-8 -*-
"""
Falcon-Eye — core/stringdata.py
Reads FalconSharedMemoryArea3 (StringData blob) to detect the active BMS theater.

StringIdentifier layout (FlightData.h):
  ThrName = 13  ← theater name, e.g. "Korea", "Balkans", "Israel"

Binary format:
  uint32 VersionNum
  uint32 NoOfStrings
  uint32 dataSize
  for each string:
    uint32 strId
    uint32 strLength   (without \\0)
    char   strData[strLength + 1]

Ported from Falcon-Pad stringdata.py — Riesu — GNU GPL v3
"""
from __future__ import annotations

import logging
import mmap
import struct
from typing import Dict, List, Optional

from core.theaters import set_active_theater

logger = logging.getLogger(__name__)

SM3_NAME      = "FalconSharedMemoryArea3"
STRID_THR_NAME = 13   # ThrName in StringIdentifier enum

_last_thr_name: str = ""


def _read_sm3() -> Optional[bytes]:
    """Read the entire FalconSharedMemoryArea3 blob, or None if unavailable."""
    try:
        sm = mmap.mmap(-1, 4 * 1024 * 1024, SM3_NAME, access=mmap.ACCESS_READ)
        # Read header to know the real size needed
        hdr = sm.read(12)
        if len(hdr) < 12:
            sm.close(); return None
        _ver, no_strings, data_size = struct.unpack_from('<III', hdr, 0)
        if no_strings == 0 or no_strings > 500 or data_size > 4 * 1024 * 1024:
            sm.close(); return None
        sm.seek(0)
        buf = sm.read(12 + data_size)
        sm.close()
        return buf
    except Exception:
        return None


def read_all_strings() -> Dict[int, List[str]]:
    """Parse FalconSharedMemoryArea3 → {strId: [str, ...]}."""
    buf = _read_sm3()
    if not buf or len(buf) < 12:
        return {}
    try:
        _ver, no_strings, data_size = struct.unpack_from('<III', buf, 0)
    except struct.error:
        return {}
    if no_strings == 0 or no_strings > 500:
        return {}

    result: Dict[int, List[str]] = {}
    off = 12
    for _ in range(no_strings):
        if off + 8 > len(buf):
            break
        try:
            str_id, str_len = struct.unpack_from('<II', buf, off)
            off += 8
            if off + str_len + 1 > len(buf):
                break
            text = buf[off:off + str_len].decode('utf-8', errors='replace')
            off += str_len + 1
            result.setdefault(str_id, []).append(text)
        except (struct.error, UnicodeDecodeError):
            break
    return result


def detect_theater() -> bool:
    """
    Read ThrName from SM3 and update the active theater.
    Returns True if the theater changed (caller may want to recentre the map).
    """
    global _last_thr_name
    strings = read_all_strings()
    entries = strings.get(STRID_THR_NAME, [])
    if not entries:
        return False
    thr_name = entries[0].strip()
    if not thr_name or thr_name == _last_thr_name:
        return False
    _last_thr_name = thr_name
    changed = set_active_theater(thr_name)
    if changed:
        logger.info(f"Theater detected from SM3: '{thr_name}'")
    return changed
