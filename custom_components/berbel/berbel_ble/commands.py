"""Command definitions for Berbel BLE module."""

from .const import *


def create_light_brightness_command(top_brightness: int = None, bottom_brightness: int = None) -> bytes:
    """
    Creates a command for the light brightness.
    
    Args:
        top_brightness: Brightness of the top light (0-255, None = do not change)
        bottom_brightness: Brightness of the bottom light (0-255, None = do not change)
    
    Returns:
        31-Byte-Command for the light control
    """
    # Basis-Kommando: 01630000TTBB00000000000000000000000000000000000000000000000000 (31 Bytes)
    command = bytearray.fromhex("01630000000000000000000000000000000000000000000000000000000000")
    
    if top_brightness is not None:
        if not 0 <= top_brightness <= 255:
            raise ValueError("top_brightness must be between 0 and 255")
        command[5] = top_brightness  # Position for the top light
    
    if bottom_brightness is not None:
        if not 0 <= bottom_brightness <= 255:
            raise ValueError("bottom_brightness must be between 0 and 255")  
        command[4] = bottom_brightness  # Position for the bottom light
    
    return bytes(command)


def create_light_brightness_command_from_percentage(top_percentage: int = None, bottom_percentage: int = None) -> bytes:
    """
    Creates a command for the light brightness from percentage values.
    
    Args:
        top_percentage: Brightness of the top light (0-100%, None = do not change)
        bottom_percentage: Brightness of the bottom light (0-100%, None = do not change)
    
    Returns:
        31-Byte-Command for the light control
    """
    top_brightness = None
    bottom_brightness = None
    
    if top_percentage is not None:
        if not 0 <= top_percentage <= 100:
            raise ValueError("top_percentage must be between 0 and 100")
        top_brightness = int(top_percentage * 2.55)
    
    if bottom_percentage is not None:
        if not 0 <= bottom_percentage <= 100:
            raise ValueError("bottom_percentage must be between 0 and 100")
        bottom_brightness = int(bottom_percentage * 2.55)
    
    return create_light_brightness_command(top_brightness, bottom_brightness)


def create_fan_command(level: int) -> bytes:
    """
    Creates a command for the fan control.
    
    Args:
        level: Fan level (0-3)
    
    Returns:
        31-Byte-Command for the fan control
    """
    if not 0 <= level <= 3:
        raise ValueError("level must be between 0 and 3")
    
    if level == 0:
        return CMD_FAN_OFF
    elif level == 1:
        return CMD_FAN_LEVEL_1
    elif level == 2:
        return CMD_FAN_LEVEL_2
    elif level == 3:
        return CMD_FAN_LEVEL_3


# Predefined commands for easy use
class LightCommands:
    """Collection of all light commands."""
    
    TOP_ON = CMD_LIGHT_TOP_ON
    TOP_OFF = CMD_LIGHT_TOP_OFF
    BOTTOM_ON = CMD_LIGHT_BOTTOM_ON
    BOTTOM_OFF = CMD_LIGHT_BOTTOM_OFF
    BOTH_ON = CMD_BOTH_LIGHTS_ON
    BOTH_OFF = CMD_BOTH_LIGHTS_OFF


class FanCommands:
    """Collection of all fan commands."""
    
    OFF = CMD_FAN_OFF
    LEVEL_1 = CMD_FAN_LEVEL_1
    LEVEL_2 = CMD_FAN_LEVEL_2
    LEVEL_3 = CMD_FAN_LEVEL_3


def validate_command_length(command: bytes) -> None:
    """
    Validates the command length.
    
    Args:
        command: The command to validate
        
    Raises:
        ValueError: If the command is not 31 bytes long
    """
    if len(command) != 31:
        raise ValueError(f"Command must be 31 bytes long, but is {len(command)} bytes") 