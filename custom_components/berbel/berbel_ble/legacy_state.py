"""Legacy state reading for older Berbel models (HOOD_PER).

Provides helpers to read TX/CF characteristics and parse ASCII payloads
based on template/sources/com/cybob/wescoremote/utils/Hood.java::evaluateResponse.
"""
from __future__ import annotations
import logging
from typing import Dict, Optional
from bleak import BleakClient

from .const import (
    LEGACY_UUID_TX,
    LEGACY_UUID_KONFIG,
)

_LOGGER = logging.getLogger(__name__)


def _safe_decode_ascii(data: bytes) -> str:
    try:
        return bytes(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _parse_tx_ascii(s: str) -> Dict:
    """Parse TX ASCII as in Hood.evaluateResponse for TX.
    Java logic:
      stufe = int(hexToString.substring(4, 5))
      hasActiveIllumination = substring(5,6) == 'L'
      hasActiveTrailing = substring(6,7) == 'N'
      hasActiveCirculation = substring(7,8) == 'M'
      hasActiveLiftUp = substring(8,9) == 'H'
      hasActiveLiftDown = substring(8,9) == 'R'
      hasActiveEffect = substring(9,10) == 'E'
      hasActiveRGB = substring(10,11) == 'B'
      hasFatFilterSaturation = substring(11,12) == 'F'
      hasCoalFilterSaturation = substring(12,13) == 'K'
      hasAutomatic = substring(14,15) == 'A'
    We only need fan level, illumination and postrun (Nachlauf N) mapping.
    """
    result = {
        "fan_level": 0,
        "fan_postrun_active": False,
        "light_top_on": False,
        "light_bottom_on": False,
    }
    if len(s) < 15:
        return result
    # Fan level at index 4 (single char number)
    try:
        level_char = s[4:5]
        result["fan_level"] = max(0, min(3, int(level_char)))
    except Exception:
        pass
    # Illumination flag 'L' at index 5
    illum = s[5:6] == "L"
    result["light_top_on"] = illum
    result["light_bottom_on"] = illum
    # Postrun 'N' at index 6
    result["fan_postrun_active"] = s[6:7] == "N"
    return result


def _parse_cf_ascii(s: str) -> Dict:
    """Parse CF ASCII. We currently do not map additional fields to HA state.
    Java indicates feature availability; we can ignore for runtime state.
    """
    return {}


async def read_legacy_state_via_gatt(client: BleakClient) -> Optional[Dict]:
    """Read legacy state via TX/CF characteristics and parse ASCII.

    Returns a dict compatible with BerbelDevice or None if not available.
    The function is best-effort and should be used as fallback when
    advertisement manufacturer data is not present.
    """
    try:
        # Some devices may not expose services until accessed; ensure services resolved
        try:
            await client.get_services()
        except Exception:
            pass

        tx_data: Optional[bytes] = None
        cf_data: Optional[bytes] = None
        # Read TX (if present)
        try:
            tx_data = await client.read_gatt_char(LEGACY_UUID_TX)
        except Exception as e:
            _LOGGER.debug("Legacy TX read failed: %s", e)
        # Read CF (optional)
        try:
            cf_data = await client.read_gatt_char(LEGACY_UUID_KONFIG)
        except Exception as e:
            _LOGGER.debug("Legacy CF read failed: %s", e)

        if tx_data is None and cf_data is None:
            return None

        result: Dict = {}
        if tx_data is not None:
            tx_str = _safe_decode_ascii(tx_data)
            parsed_tx = _parse_tx_ascii(tx_str)
            result.update(parsed_tx)
        if cf_data is not None:
            cf_str = _safe_decode_ascii(cf_data)
            parsed_cf = _parse_cf_ascii(cf_str)
            result.update(parsed_cf)

        # Fill brightness/color unknowns explicitly
        if "light_top_brightness" not in result:
            result["light_top_brightness"] = 0
        if "light_bottom_brightness" not in result:
            result["light_bottom_brightness"] = 0
        if "light_top_color" not in result:
            result["light_top_color"] = 0
        if "light_bottom_color" not in result:
            result["light_bottom_color"] = 0

        return result
    except Exception as e:
        _LOGGER.debug("Legacy GATT state read failed: %s", e)
        return None
