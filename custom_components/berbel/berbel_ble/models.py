"""Data models for the Berbel BLE module."""

from __future__ import annotations
import dataclasses
from .const import MAX_KELVIN, MIN_KELVIN


@dataclasses.dataclass
class BerbelDevice:
    """Response data with information about the Berbel device"""

    name: str = ""
    address: str = ""
    light_top_on: bool = False
    light_bottom_on: bool = False
    light_top_brightness: int = 0      # 0-100%
    light_bottom_brightness: int = 0   # 0-100%
    light_top_color: int = 0           # 0-100%
    light_bottom_color: int = 0        # 0-100%
    fan_level: int = 0
    fan_postrun_active: bool = False

    def __post_init__(self):
        """Validates the values after initialization."""
        self.light_top_brightness = max(0, min(100, self.light_top_brightness))
        self.light_bottom_brightness = max(0, min(100, self.light_bottom_brightness))
        self.light_top_color = max(0, min(100, self.light_top_color))
        self.light_bottom_color = max(0, min(100, self.light_bottom_color))
        self.fan_level = max(0, min(4, self.fan_level))

    @property
    def light_top_color_kelvin(self) -> int:
        """Converts the top light color from percentage to Kelvin."""
        # 0% = 6500K, 100% = 2700K, linear dazwischen
        return int(round(MAX_KELVIN - (self.light_top_color / 100) * (MAX_KELVIN - MIN_KELVIN)))

    @property
    def light_bottom_color_kelvin(self) -> int:
        """Converts the bottom light color from percentage to Kelvin."""
        return int(round(MAX_KELVIN - (self.light_bottom_color / 100) * (MAX_KELVIN - MIN_KELVIN)))

    def __str__(self) -> str:
        """User-friendly string representation."""
        return (f"BerbelDevice(name='{self.name}', address='{self.address}', "
                f"light_top_on={self.light_top_on}, light_bottom_on={self.light_bottom_on}, "
                f"light_top_brightness={self.light_top_brightness}, "
                f"light_bottom_brightness={self.light_bottom_brightness}, "
                f"light_top_color={self.light_top_color}, "
                f"light_bottom_color={self.light_bottom_color}, "
                f"fan_level={self.fan_level}, fan_postrun_active={self.fan_postrun_active})") 