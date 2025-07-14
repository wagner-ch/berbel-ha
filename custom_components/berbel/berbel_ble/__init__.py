"""Berbel BLE Integration - Modular und saubere Architektur."""

from __future__ import annotations

# Haupt-Klassen und -Modelle
from .models import BerbelDevice
from .client import BerbelBluetoothDeviceData
from .parser import BerbelBluetoothDeviceParser

# Kommandos und Konstanten
from .commands import (
    create_light_brightness_command_from_percentage,
    LightCommands,
    FanCommands
)

# Version
__version__ = "0.1.0"

# Haupt-Exports
__all__ = [
    # Hauptklassen
    "BerbelDevice",
    "BerbelBluetoothDeviceData", 
    "BerbelBluetoothDeviceParser",
    
    # Kommando-Funktionen
    "create_light_brightness_command_from_percentage", 
    "LightCommands",
    "FanCommands",
] 