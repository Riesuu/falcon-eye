# -*- coding: utf-8 -*-
"""
BMS SharedMemory reader — FalconSharedMemoryArea2
Reads UHF/VHF radio frequencies from BMS cockpit.

Offsets verified against BMS 4.37/4.38 FlightData.h:
  0x030 = UHFChannel  (int)   preset number 1-20
  0x034 = VHFChannel  (int)   preset number  
  0x038 = UHFFreq     (float) frequency in MHz, e.g. 339.750
  0x03C = VHFFreq     (float) frequency in MHz, e.g. 127.500
  0x408 = latitude    (float) degrees
  0x40C = longitude   (float) degrees
"""
import struct
import logging

logger = logging.getLogger(__name__)

SM_NAME = "FalconSharedMemoryArea2"
SM_SIZE = 0x1000

OFF_UHF_CHANNEL = 0x030  # int   - UHF preset channel (1-20)
OFF_VHF_CHANNEL = 0x034  # int   - VHF preset channel
OFF_UHF_FREQ    = 0x038  # float - UHF frequency in MHz (e.g. 339.750)
OFF_VHF_FREQ    = 0x03C  # float - VHF frequency in MHz (e.g. 127.500)
OFF_LAT         = 0x408  # float - latitude degrees
OFF_LON         = 0x40C  # float - longitude degrees


def _read_sm(name: str, size: int):
    try:
        import mmap
        sm = mmap.mmap(-1, size, name, access=mmap.ACCESS_READ)
        buf = sm.read(size)
        sm.close()
        return buf
    except Exception:
        return None


def is_bms_running() -> bool:
    try:
        import mmap
        sm = mmap.mmap(-1, 4, SM_NAME, access=mmap.ACCESS_READ)
        sm.close()
        return True
    except Exception:
        return False


# BMS IVC frequencies snap to 25 kHz steps (e.g. 339.750, 305.000)
# Round to nearest 25 kHz to eliminate float noise from SharedMemory
_FREQ_STEP = 0.025  # MHz

def format_freq(mhz: float) -> str:
    """Format MHz float to display string, snapped to 25 kHz grid.
    339.7499... -> '339.750', 305.0001... -> '305.000'
    """
    if not mhz or mhz < 100.0 or mhz > 500.0:
        return ""
    # Snap to nearest 25 kHz step to eliminate float noise
    snapped = round(round(mhz / _FREQ_STEP) * _FREQ_STEP, 3)
    return f"{snapped:.3f}"


def get_radio_data():
    """Read radio and position data from BMS SharedMemory.
    Returns dict or None if BMS not running.
    """
    buf = _read_sm(SM_NAME, SM_SIZE)
    if not buf or len(buf) < 0x450:
        return None

    result = {}
    try:
        uhf_ch  = struct.unpack_from("<i", buf, OFF_UHF_CHANNEL)[0]
        vhf_ch  = struct.unpack_from("<i", buf, OFF_VHF_CHANNEL)[0]
        uhf_mhz = struct.unpack_from("<f", buf, OFF_UHF_FREQ)[0]
        vhf_mhz = struct.unpack_from("<f", buf, OFF_VHF_FREQ)[0]
        lat     = struct.unpack_from("<f", buf, OFF_LAT)[0]
        lon     = struct.unpack_from("<f", buf, OFF_LON)[0]

        uhf_str = format_freq(uhf_mhz)
        vhf_str = format_freq(vhf_mhz)

        result["uhf_freq"]    = uhf_str
        result["vhf_freq"]    = vhf_str
        result["uhf_channel"] = uhf_ch if 1 <= uhf_ch <= 20 else 0
        result["vhf_channel"] = vhf_ch if 1 <= vhf_ch <= 20 else 0

        if abs(lat) > 0.1:
            result["lat"] = float(lat)
            result["lon"] = float(lon)

        logger.debug(f"SM: UHF={uhf_str}(ch{uhf_ch}) VHF={vhf_str}(ch{vhf_ch})")

    except Exception as e:
        logger.debug(f"SM parse error: {e}")
        return None

    return result if result else None
