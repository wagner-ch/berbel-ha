"""Status-Parsing for the Berbel BLE module."""

from __future__ import annotations
import logging
from .const import *
from .models import BerbelDevice

_LOGGER = logging.getLogger(__name__)

# Byte-Positionen für bessere Lesbarkeit
STATUS_FAN_LEVEL_1_BYTE = 0
STATUS_FAN_LEVEL_2_4_BYTE = 1
STATUS_LIGHT_TOP_BYTE = 2
STATUS_LIGHT_BOTTOM_BYTE = 4
STATUS_POSTRUN_BYTE = 5

BRIGHTNESS_BOTTOM_BYTE = 4
BRIGHTNESS_TOP_BYTE = 5

COLOR_BOTTOM_BYTE = 6
COLOR_TOP_BYTE = 7


class BerbelBluetoothDeviceParser:
    """
    Helper class to parse BLE status data.
    
    Byte-Layout:
    Status:
    - Byte 0: Fan Level 1 (0x10)
    - Byte 1: Fan Level 2-4 (0x10, 0x18, 0x19)
    - Byte 2: Light Top Status (0x10)
    - Byte 4: Light Bottom Status (0x10)
    - Byte 5: Postrun Status (0x90)
    
    Brightness:
    - Byte 4: Bottom Light Brightness (0-255)
    - Byte 5: Top Light Brightness (0-255)
    
    Colors:
    - Byte 6: Bottom Light Color (0-255)
    - Byte 7: Top Light Color (0-255)
    """

    @staticmethod
    def _parse_light_status(status: bytes) -> tuple[bool, bool]:
        """Parses the light status from the status bytes."""
        light_top_on = (status[STATUS_LIGHT_TOP_BYTE] & LIGHT_ON_MASK) != 0
        light_bottom_on = (status[STATUS_LIGHT_BOTTOM_BYTE] & LIGHT_ON_MASK) != 0
        return light_top_on, light_bottom_on

    @staticmethod
    def _parse_fan_level(status: bytes) -> int:
        """Parses the fan level from the status bytes."""
        if status[STATUS_FAN_LEVEL_1_BYTE] == FAN_LEVEL_1:
            return 1
        elif status[STATUS_FAN_LEVEL_2_4_BYTE] == FAN_LEVEL_2:
            return 2
        elif status[STATUS_FAN_LEVEL_2_4_BYTE] == FAN_LEVEL_3:
            return 3
        elif status[STATUS_FAN_LEVEL_2_4_BYTE] == FAN_LEVEL_4:
            return 4
        return 0

    @staticmethod
    def _parse_postrun_status(status: bytes) -> bool:
        """Parses the postrun status from the status bytes."""
        return (status[STATUS_POSTRUN_BYTE] & POSTRUN_MASK) == POSTRUN_MASK

    @staticmethod
    def _parse_brightness(brightness: bytes) -> tuple[int, int]:
        """Parses the brightness values from the brightness bytes."""
        if len(brightness) >= max(BRIGHTNESS_BOTTOM_BYTE, BRIGHTNESS_TOP_BYTE) + 1:
            light_bottom_brightness = int(brightness[BRIGHTNESS_BOTTOM_BYTE] / 255 * 100)
            light_top_brightness = int(brightness[BRIGHTNESS_TOP_BYTE] / 255 * 100)
        else:
            light_bottom_brightness = 0
            light_top_brightness = 0
        return light_bottom_brightness, light_top_brightness

    @staticmethod
    def _parse_colors(colors: bytes) -> tuple[int, int]:
        """Parses the color values from the colors bytes."""
        if len(colors) >= max(COLOR_BOTTOM_BYTE, COLOR_TOP_BYTE) + 1:
            light_bottom_color = int(colors[COLOR_BOTTOM_BYTE] / 255 * 100)
            light_top_color = int(colors[COLOR_TOP_BYTE] / 255 * 100)
        else:
            light_bottom_color = 0
            light_top_color = 0
        return light_bottom_color, light_top_color

    @staticmethod
    def parse_status(status: bytes, brightness: bytes, colors: bytes) -> dict:
        """Parses all status data from the BLE bytes."""
        light_top_on, light_bottom_on = BerbelBluetoothDeviceParser._parse_light_status(status)
        fan_level = BerbelBluetoothDeviceParser._parse_fan_level(status)
        fan_postrun_active = BerbelBluetoothDeviceParser._parse_postrun_status(status)
        light_bottom_brightness, light_top_brightness = BerbelBluetoothDeviceParser._parse_brightness(brightness)
        light_bottom_color, light_top_color = BerbelBluetoothDeviceParser._parse_colors(colors)

        return {
            "light_top_on": light_top_on,
            "light_bottom_on": light_bottom_on,
            "light_top_brightness": light_top_brightness,
            "light_bottom_brightness": light_bottom_brightness,
            "light_top_color": light_top_color,
            "light_bottom_color": light_bottom_color,
            "fan_level": fan_level,
            "fan_postrun_active": fan_postrun_active,
        }

    @staticmethod
    def create_device_from_data(name: str, address: str, data: dict) -> BerbelDevice:
        """Creates a BerbelDevice from parsed data."""
        return BerbelDevice(
            name=name,
            address=address,
            **data
        ) 