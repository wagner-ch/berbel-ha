"""Legacy advertisement parser for older Berbel models (HOOD_PER).

Parses manufacturer data according to template/sources/com/cybob/wescoremote/utils/Hood.java
so that we can populate a BerbelDevice-compatible dict.
"""
from __future__ import annotations
import logging
from typing import Dict, Optional, Union

_LOGGER = logging.getLogger(__name__)


def _nibble(hex_str: str, start: int) -> int:
    """Returns integer value of one hex nibble (single hex char)."""
    if len(hex_str) <= start:
        return 0
    return int(hex_str[start:start+1], 16)


def _byte(hex_str: str, start: int) -> int:
    """Returns integer value of one hex byte (two hex chars)."""
    if len(hex_str) <= start+1:
        return 0
    return int(hex_str[start:start+2], 16)


def parse_legacy_manufacturer_data(manufacturer_data: Union[bytes, str]) -> Optional[Dict]:
    """Parse legacy manufacturer data and return fields compatible with BerbelDevice.

    The Java code treats the manufacturer data as a hex string and reads specific
    nibbles/bytes:
      - Fan level: hex[12:14] (one byte)
      - Various flags spread over hex[14], [15], [16], [17] (nibbles)
      - Kennlinie: hex[18:20] (byte)
      - Feature flags: hex[22] and hex[23] (nibbles)
      - Operating hours: hex[24:28] (2 bytes, optional)

    We map to:
      - fan_level: 0-3 (cap at 3; value 4 is treated as 3)
      - light_top_on / light_bottom_on: approximated from flags (no split available, use illumination/effect as best-effort)
      - fan_postrun_active: from hasActiveTrailing
      - brightness/color percentages are unknown from advertisement => 0
    """
    try:
        if isinstance(manufacturer_data, bytes):
            hex_str = manufacturer_data.hex()
        else:
            hex_str = manufacturer_data.replace(" ", "").lower()

        if len(hex_str) < 18:  # need at least up to index 17 nibble
            return None

        # Fan level (0-3 typical)
        fan_level = _byte(hex_str, 12)
        if fan_level > 3:
            # some firmwares may report 4 for intensive; cap to 3 for HA range
            fan_level = 3

        # Nibble groups
        n14 = _nibble(hex_str, 14)
        n15 = _nibble(hex_str, 15)
        n16 = _nibble(hex_str, 16)
        n17 = _nibble(hex_str, 17)
        # n18-19 is kennlinie (unused here)
        # feature nibbles
        n22 = _nibble(hex_str, 22)
        n23 = _nibble(hex_str, 23)

        # Flags per Hood.java mapping
        hasActiveIllumination = bool(n17 & 0b0001)
        hasActiveTrailing = bool(n17 & 0b0010)
        hasActiveCirculation = bool(n17 & 0b0100)
        hasActiveLiftUp = bool(n17 & 0b1000)

        hasActiveLiftDown = bool(n16 & 0b0001)
        hasActiveEffect = bool(n16 & 0b0010)
        hasActiveRGB = bool(n16 & 0b0100)
        hasFatFilterSaturation = bool(n16 & 0b1000)

        hasCoalFilterSaturation = bool(n15 & 0b0001)
        hasAutomatic = bool(n15 & 0b1000)
        hasActiveAutoRunReset = bool(n14 & 0b0001)

        hasEffectLight = bool(n23 & 0b0001)
        hasCirculation = bool(n23 & 0b0010)
        hasRGB = bool(n23 & 0b0100)
        hasLift = bool(n23 & 0b1000)

        hasDimmer = bool(n22 & 0b0010)
        hasAutoTrailing = bool(n22 & 0b0100)
        hasIntensive = bool(n22 & 0b1000)

        # Map to BerbelDevice fields
        data = {
            "fan_level": fan_level,
            "fan_postrun_active": hasActiveTrailing,
            # We do not know split top/bottom from broadcast; assume illumination -> both on
            "light_top_on": hasActiveIllumination or hasEffectLight,
            "light_bottom_on": hasActiveIllumination or hasEffectLight,
            "light_top_brightness": 0,
            "light_bottom_brightness": 0,
            "light_top_color": 0,
            "light_bottom_color": 0,
        }

        _LOGGER.debug(
            "Legacy parsed: fan=%s, postrun=%s, illum=%s, effect=%s, auto=%s",
            fan_level, hasActiveTrailing, hasActiveIllumination, hasEffectLight, hasAutomatic,
        )
        return data
    except Exception as e:
        _LOGGER.error("Legacy manufacturer data parse error: %s", e)
        return None
