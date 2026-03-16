# -*- coding: utf-8 -*-
"""
BMS SharedMemory reader — reads FlightData2 for radio freqs and pilot list.
Reference offsets from BMS_GPS_LOCAL_FINAL_21.py and FlightData.h (BMS 4.38).
"""
import struct
import logging

logger = logging.getLogger(__name__)

SM_FD2 = "FalconSharedMemoryArea2"
SM_SIZE = 0x1000


def _read_sm(name, size):
    try:
        import mmap
        sm = mmap.mmap(-1, size, name, access=mmap.ACCESS_READ)
        buf = sm.read(size)
        sm.close()
        return buf
    except Exception:
        return None


def is_bms_running():
    try:
        import mmap
        sm = mmap.mmap(-1, 4, SM_FD2, access=mmap.ACCESS_READ)
        sm.close()
        return True
    except Exception:
        return False


def get_radio_data():
    """Read radio data from BMS SharedMemory.
    Returns dict with lat, lon or None if BMS not running."""
    buf = _read_sm(SM_FD2, SM_SIZE)
    if not buf or len(buf) < 0x500:
        return None
    result = {}
    try:
        lat = struct.unpack_from('<f', buf, 0x408)[0]
        lon = struct.unpack_from('<f', buf, 0x40C)[0]
        if abs(lat) > 0.1:
            result["lat"] = lat
            result["lon"] = lon
    except Exception as e:
        logger.debug(f"SM parse: {e}")
    return result if result else None


def format_freq(raw_int):
    """Format BMS frequency int: 339750 -> '339.750'"""
    if not raw_int or raw_int <= 0:
        return ""
    s = str(raw_int)
    if len(s) >= 4:
        return s[:-3] + "." + s[-3:]
    return s
