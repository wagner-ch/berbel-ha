"""Constants for the Berbel Skyline Edge Base integration."""
from __future__ import annotations

from typing import Final

# Integration domain
DOMAIN: Final = "berbel"

# Update interval in seconds (optimiert für Connection-Pooling mit 20s Timeout)
UPDATE_INTERVAL: Final = 18

# Device manufacturer
MANUFACTURER: Final = "Berbel"

# Supported device models (primary target: Skyline Edge Base)
SUPPORTED_MODELS: Final = ["SKE", "BERBEL", "HOOD_PER"]

# Entity suffixes
FAN_SUFFIX: Final = "Fan"
LIGHT_TOP_SUFFIX: Final = "Light Top"
LIGHT_BOTTOM_SUFFIX: Final = "Light Bottom"
SWITCH_POSTRUN_SUFFIX: Final = "Nachlauf"

# Attributes
ATTR_FAN_POSTRUN: Final = "postrun_active"
ATTR_COLOR_TEMP_KELVIN: Final = "color_temp_kelvin"
