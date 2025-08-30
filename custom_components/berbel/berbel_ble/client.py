"""BLE client for the Berbel BLE module."""

from __future__ import annotations
import asyncio
import logging
from typing import Optional
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import *
from .models import BerbelDevice
from .parser import BerbelBluetoothDeviceParser
from .legacy_parser import parse_legacy_manufacturer_data
from .legacy_commands import LegacyCommandSender
from .commands import (
    create_light_brightness_command_from_percentage,
    validate_command_length,
    LightCommands,
    FanCommands
)

_LOGGER = logging.getLogger(__name__)

# Byte positions for color changes
COLOR_BOTTOM_BYTE = 6
COLOR_TOP_BYTE = 7

# Connection Pool Settings
CONNECTION_TIMEOUT = 20.0  # Keep connection open for 20 seconds for regular updates
COMMAND_DELAY = 0.1  # Short pause between commands


class BerbelBluetoothDeviceData:
    """BLE client for Berbel range hoods with optimized connection management."""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or _LOGGER
        self._active_client: Optional[BleakClient] = None
        self._active_device: Optional[BLEDevice] = None
        self._connection_timeout_handle: Optional[asyncio.Handle] = None
        self._connection_lock = asyncio.Lock()
        self._disconnect_pending = False
        self._legacy_mode: bool = False

    async def _ensure_connection(self, ble_device: BLEDevice) -> BleakClient:
        """Ensures an active BLE connection exists or establishes one."""
        # Check if we already have a valid connection to the same device
        if (self._active_client and
            self._active_client.is_connected and
            self._active_device and
            self._active_device.address == ble_device.address and
            not self._disconnect_pending):

            self.logger.debug("BLE-Client: Using existing connection")
            # Extend timeout
            self._schedule_disconnect()
            return self._active_client

        # Disconnect old connection if present
        if self._active_client:
            self.logger.debug("BLE-Client: Disconnecting old connection")
            await self._disconnect_internal()

        # Establish new connection
        self.logger.debug("BLE-Client: Establishing new connection...")
        client = await establish_connection(BleakClient, ble_device, ble_device.address)

        self._active_client = client
        self._active_device = ble_device
        self._disconnect_pending = False

        # Schedule auto-disconnect after timeout
        self._schedule_disconnect()

        self.logger.debug("BLE-Client: New connection established and cached")
        return client

    def _schedule_disconnect(self):
        """Schedules automatic disconnection after timeout."""
        if self._connection_timeout_handle:
            self._connection_timeout_handle.cancel()

        def disconnect_callback():
            """Callback for automatic disconnection."""
            if not self._disconnect_pending:
                self._disconnect_pending = True
                asyncio.create_task(self._disconnect_internal())

        loop = asyncio.get_event_loop()
        self._connection_timeout_handle = loop.call_later(
            CONNECTION_TIMEOUT,
            disconnect_callback
        )

    async def _disconnect_internal(self):
        """Disconnects the internal connection."""
        if self._connection_timeout_handle:
            self._connection_timeout_handle.cancel()
            self._connection_timeout_handle = None

        if self._active_client:
            try:
                await self._active_client.disconnect()
                self.logger.debug("BLE-Client: Connection disconnected")
            except Exception as e:
                self.logger.debug(f"BLE-Client: Error during disconnect: {e}")
            finally:
                self._active_client = None
                self._active_device = None
                self._disconnect_pending = False

    async def _get_status(self, client: BleakClient, device: BerbelDevice) -> BerbelDevice:
        """Reads status data from BLE device and updates the device object."""
        # Legacy devices: try to parse advertisement manufacturer data exposed by Bleak device metadata
        if self._legacy_mode:
            try:
                adv = None
                if hasattr(self._active_device, "metadata") and isinstance(self._active_device.metadata, dict):
                    # bleak stores manufacturer_data as {company_id: bytes}
                    mfd = self._active_device.metadata.get("manufacturer_data") or {}
                    if isinstance(mfd, dict) and len(mfd) > 0:
                        # Use the first entry
                        adv = next(iter(mfd.values()))
                data = parse_legacy_manufacturer_data(adv) if adv is not None else None
                if data:
                    for key, value in data.items():
                        setattr(device, key, value)
                    return device
                else:
                    raise NotImplementedError("Legacy advertisement data not available to parse")
            except Exception as e:
                self.logger.warning(f"Legacy parsing failed or not available: {e}")
                # Fallback to returning whatever we have (mostly defaults)
                return device
        try:
            status = await client.read_gatt_char(READ_STATE)
            brightness = await client.read_gatt_char(READ_WRITE_LIGHT_BRIGHTNESS)
            colors = await client.read_gatt_char(READ_WRITE_LIGHT_COLOR)

            self.logger.debug("Status data received:")
            self.logger.debug(f"Status: {status.hex()}")
            self.logger.debug(f"Brightness: {brightness.hex()}")
            self.logger.debug(f"Colors: {colors.hex()}")

            data = BerbelBluetoothDeviceParser.parse_status(status, brightness, colors)

            # Simple assignment of parsed data
            for key, value in data.items():
                setattr(device, key, value)

            self.logger.info(
                f"Device Status: Fan={device.fan_level}, Postrun={device.fan_postrun_active}, "
                f"Top Light={device.light_top_on}({device.light_top_brightness}%, {device.light_top_color_kelvin}K), "
                f"Bottom Light={device.light_bottom_on}({device.light_bottom_brightness}%, {device.light_bottom_color_kelvin}K)"
            )

            return device

        except BleakError as e:
            self.logger.error(f"BLE error reading data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error reading status: {e}")
            raise

    def _detect_legacy(self, ble_device: BLEDevice) -> bool:
        """Detect if the device is an older-model (legacy) hood.
        Heuristics: device name equals DEFAULT_LEGACY_DEVICE_NAME or service UUID matches legacy ones (if available).
        """
        try:
            name = (ble_device.name or "").upper()
            if DEFAULT_LEGACY_DEVICE_NAME in name:
                return True
            # Bleak may provide advertised service UUIDs in metadata
            uuids = []
            if hasattr(ble_device, "metadata") and isinstance(ble_device.metadata, dict):
                uuids = [u.lower() for u in (ble_device.metadata.get("uuids") or [])]
            legacy_candidates = {
                LEGACY_UUID_SERVICE.lower(),
                LEGACY_UUID_SERVICE_2018.lower(),
            }
            return any(u in legacy_candidates for u in uuids)
        except Exception:
            return False

    async def update_device(self, ble_device: BLEDevice, max_retries: int = 2) -> BerbelDevice:
        """Connects to device via BLE and retrieves relevant data."""
        self.logger.info(f"BLE-Client: update_device called - Device: {ble_device.address}")

        if ble_device is None:
            raise ValueError("BLEDevice cannot be None")

        # Detect legacy mode early
        self._legacy_mode = self._detect_legacy(ble_device)
        if self._legacy_mode:
            # For legacy devices, full state is broadcast via manufacturer data (not currently parsed here).
            # We raise a clear error to hint configuration until parser support is added.
            self.logger.warning(
                "Legacy Berbel hood detected (older model using HOOD_PER/legacy service UUIDs). "
                "Status reading via GATT is not supported yet in this integration."
            )

        # Legacy devices do not require a GATT connection to read status; avoid connecting
        if self._legacy_mode:
            device = BerbelDevice(name=ble_device.name or "", address=ble_device.address)
            try:
                # Populate from manufacturer data only
                adv = None
                if hasattr(ble_device, "metadata") and isinstance(ble_device.metadata, dict):
                    mfd = ble_device.metadata.get("manufacturer_data") or {}
                    if isinstance(mfd, dict) and len(mfd) > 0:
                        adv = next(iter(mfd.values()))
                data = parse_legacy_manufacturer_data(adv) if adv is not None else None
                if data:
                    for k, v in data.items():
                        setattr(device, k, v)
                    self.logger.info("BLE-Client: Legacy status parsed from advertisements (no GATT connection).")
                    return device
                else:
                    self.logger.warning("BLE-Client: Legacy manufacturer data not available; returning defaults.")
                    return device
            finally:
                # Ensure no pooled connection remains
                await self._disconnect_internal()

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                async with self._connection_lock:
                    client = await self._ensure_connection(ble_device)

                    device = BerbelDevice(
                        name=ble_device.name or "",
                        address=ble_device.address
                    )

                    self.logger.debug(f"BLE-Client: Reading status data... (attempt {attempt}/{max_retries})")
                    device = await self._get_status(client, device)

                    self.logger.info("BLE-Client: Data query successful")
                    return device

            except Exception as e:
                last_exception = e
                self.logger.warning(f"BLE-Client: Status update attempt {attempt}/{max_retries} failed: {e}")

                # Immediately disconnect on connection errors
                if isinstance(e, BleakError):
                    await self._disconnect_internal()

                # Short pause before next attempt
                if attempt < max_retries:
                    await asyncio.sleep(1)

        # Last attempt failed - disconnect connection
        await self._disconnect_internal()
        self.logger.error(f"BLE-Client: All {max_retries} status update attempts failed")
        raise last_exception if last_exception else RuntimeError("Status update failed")

    async def _execute_command(self, ble_device: BLEDevice, command: bytes) -> None:
        """Executes a command on the BLE device with optimized connection."""
        self.logger.info(f"BLE-Client: _execute_command called - Device: {ble_device.address}, Command: {command.hex()}")

        if ble_device is None:
            raise ValueError("BLEDevice cannot be None")

        validate_command_length(command)
        self.logger.debug(f"BLE-Client: Command length validated: {len(command)} bytes")

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Short wait for BLE stability
                await asyncio.sleep(COMMAND_DELAY)

                if self._legacy_mode:
                    # Older models expect URL-encoded ASCII commands written to RX.
                    # This integration currently uses binary commands for modern models.
                    # TODO: Implement mapping to legacy ASCII commands (see template Hood.java and R.java cmd_* strings).
                    self.logger.error(
                        "Legacy model detected: Command execution requires ASCII commands via RX (PIN+command). "
                        "This is not implemented yet."
                    )
                    raise NotImplementedError("Legacy command execution not implemented")

                self.logger.debug(f"BLE-Client: Sending command to UUID: {WRITE_COMMANDS}")
                await client.write_gatt_char(WRITE_COMMANDS, command)
                self.logger.debug(f"BLE-Client: Command written successfully")

                self.logger.info(f"BLE-Client: Command {command.hex()} sent successfully")

            except Exception as e:
                self.logger.error(f"BLE-Client: Command execution failed: {e}")
                # Disconnect on errors
                await self._disconnect_internal()
                raise

    async def _execute_command_with_status(self, ble_device: BLEDevice, command: bytes) -> BerbelDevice:
        """Executes a command and immediately reads status in one connection."""
        self.logger.info(f"BLE-Client: _execute_command_with_status called - Device: {ble_device.address}")

        if ble_device is None:
            raise ValueError("BLEDevice cannot be None")

        validate_command_length(command)

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Send command
                await asyncio.sleep(COMMAND_DELAY)
                await client.write_gatt_char(WRITE_COMMANDS, command)
                self.logger.debug(f"BLE-Client: Command sent: {command.hex()}")

                # Wait briefly for device to update status
                await asyncio.sleep(0.2)

                # Read status
                device = BerbelDevice(
                    name=ble_device.name or "",
                    address=ble_device.address
                )
                device = await self._get_status(client, device)

                self.logger.info(f"BLE-Client: Command and status update successful")
                return device

            except Exception as e:
                self.logger.error(f"BLE-Client: Command+status failed: {e}")
                await self._disconnect_internal()
                raise

    # === OPTIMIZED LIGHT CONTROL ===

    async def set_light_top_on(self, ble_device: BLEDevice, on: bool = True) -> None:
        """Turns the top light on or off while maintaining bottom light state."""
        # Fast method: Read current status and then command in one connection
        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read status
                device = BerbelDevice(name=ble_device.name or "", address=ble_device.address)
                device = await self._get_status(client, device)

                # Generate command
                current_bottom = device.light_bottom_brightness if device.light_bottom_on else 0
                top_brightness = 100 if on else 0

                command = create_light_brightness_command_from_percentage(
                    top_percentage=top_brightness,
                    bottom_percentage=current_bottom
                )

                # Send command
                await asyncio.sleep(COMMAND_DELAY)
                await client.write_gatt_char(WRITE_COMMANDS, command)

                self.logger.info(f"BLE-Client: Top light turned {'on' if on else 'off'}")

            except Exception as e:
                self.logger.error(f"BLE-Client: Top light switching failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_light_bottom_on(self, ble_device: BLEDevice, on: bool = True) -> None:
        """Turns the bottom light on or off while maintaining top light state."""
        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read status
                device = BerbelDevice(name=ble_device.name or "", address=ble_device.address)
                device = await self._get_status(client, device)

                # Generate command
                current_top = device.light_top_brightness if device.light_top_on else 0
                bottom_brightness = 100 if on else 0

                command = create_light_brightness_command_from_percentage(
                    top_percentage=current_top,
                    bottom_percentage=bottom_brightness
                )

                # Send command
                await asyncio.sleep(COMMAND_DELAY)
                await client.write_gatt_char(WRITE_COMMANDS, command)

                self.logger.info(f"BLE-Client: Bottom light turned {'on' if on else 'off'}")

            except Exception as e:
                self.logger.error(f"BLE-Client: Bottom light switching failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_both_lights_on(self, ble_device: BLEDevice, on: bool = True) -> None:
        """Turns both lights on or off."""
        top_brightness = 100 if on else 0
        bottom_brightness = 100 if on else 0

        if self._legacy_mode:
            async with self._connection_lock:
                client = await self._ensure_connection(ble_device)
                sender = LegacyCommandSender()
                if on:
                    await sender.lights_on(client)
                else:
                    await sender.lights_off(client)
                return

        command = create_light_brightness_command_from_percentage(
            top_percentage=top_brightness,
            bottom_percentage=bottom_brightness
        )
        await self._execute_command(ble_device, command)

    async def set_light_top_brightness(self, ble_device: BLEDevice, brightness_percentage: int) -> None:
        """Sets the brightness of the top light (0-100%) - optimized."""
        self.logger.info(f"BLE-Client: set_light_top_brightness called - Brightness: {brightness_percentage}%, Device: {ble_device.address}")

        if not 0 <= brightness_percentage <= 100:
            raise ValueError("brightness_percentage must be between 0 and 100")

        # Optimized version: Read status and command in one connection
        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read status to maintain bottom light
                device = BerbelDevice(name=ble_device.name or "", address=ble_device.address)
                device = await self._get_status(client, device)

                current_bottom = device.light_bottom_brightness if device.light_bottom_on else 0
                self.logger.debug(f"BLE-Client: Current bottom brightness: {current_bottom}%")

                command = create_light_brightness_command_from_percentage(
                    top_percentage=brightness_percentage,
                    bottom_percentage=current_bottom
                )
                self.logger.debug(f"BLE-Client: Light command generated: {command.hex()}")

                # Send command
                await asyncio.sleep(COMMAND_DELAY)
                await client.write_gatt_char(WRITE_COMMANDS, command)

                self.logger.info(f"BLE-Client: Top brightness set to {brightness_percentage}%")

            except Exception as e:
                self.logger.error(f"BLE-Client: Setting top brightness failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_light_bottom_brightness(self, ble_device: BLEDevice, brightness_percentage: int) -> None:
        """Sets the brightness of the bottom light (0-100%) - optimized."""
        self.logger.info(f"BLE-Client: set_light_bottom_brightness called - Brightness: {brightness_percentage}%, Device: {ble_device.address}")

        if not 0 <= brightness_percentage <= 100:
            raise ValueError("brightness_percentage must be between 0 and 100")

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read status to maintain top light
                device = BerbelDevice(name=ble_device.name or "", address=ble_device.address)
                device = await self._get_status(client, device)

                current_top = device.light_top_brightness if device.light_top_on else 0
                self.logger.debug(f"BLE-Client: Current top brightness: {current_top}%")

                command = create_light_brightness_command_from_percentage(
                    top_percentage=current_top,
                    bottom_percentage=brightness_percentage
                )
                self.logger.debug(f"BLE-Client: Light command generated: {command.hex()}")

                # Send command
                await asyncio.sleep(COMMAND_DELAY)
                await client.write_gatt_char(WRITE_COMMANDS, command)

                self.logger.info(f"BLE-Client: Bottom brightness set to {brightness_percentage}%")

            except Exception as e:
                self.logger.error(f"BLE-Client: Setting bottom brightness failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_both_lights_brightness(self, ble_device: BLEDevice, top_brightness: int, bottom_brightness: int) -> None:
        """Sets the brightness of both lights simultaneously (0-100%)."""
        if not 0 <= top_brightness <= 100:
            raise ValueError("top_brightness must be between 0 and 100")
        if not 0 <= bottom_brightness <= 100:
            raise ValueError("bottom_brightness must be between 0 and 100")

        command = create_light_brightness_command_from_percentage(
            top_percentage=top_brightness,
            bottom_percentage=bottom_brightness
        )
        await self._execute_command(ble_device, command)

    # === COLOR CONTROL (simplified) ===

    async def set_light_top_color(self, ble_device: BLEDevice, color_percentage: int) -> None:
        """Sets the color of the top light (0-100%, 0=6500K, 100=2700K)."""
        if not 0 <= color_percentage <= 100:
            raise ValueError("color_percentage must be between 0 and 100")

        color_value = int(color_percentage * 255 / 100)

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read current color values
                current_colors = await client.read_gatt_char(READ_WRITE_LIGHT_COLOR)
                new_colors = bytearray(current_colors)
                if len(new_colors) > COLOR_TOP_BYTE:
                    new_colors[COLOR_TOP_BYTE] = color_value

                await client.write_gatt_char(READ_WRITE_LIGHT_COLOR, bytes(new_colors))
                self.logger.info(f"Top light color set to {color_percentage}%")

            except Exception as e:
                self.logger.error(f"BLE-Client: Setting top color failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_light_bottom_color(self, ble_device: BLEDevice, color_percentage: int) -> None:
        """Sets the color of the bottom light (0-100%, 0=6500K, 100=2700K)."""
        if not 0 <= color_percentage <= 100:
            raise ValueError("color_percentage must be between 0 and 100")

        color_value = int(color_percentage * 255 / 100)

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read current color values
                current_colors = await client.read_gatt_char(READ_WRITE_LIGHT_COLOR)
                new_colors = bytearray(current_colors)
                if len(new_colors) > COLOR_BOTTOM_BYTE:
                    new_colors[COLOR_BOTTOM_BYTE] = color_value

                await client.write_gatt_char(READ_WRITE_LIGHT_COLOR, bytes(new_colors))
                self.logger.info(f"Bottom light color set to {color_percentage}%")

            except Exception as e:
                self.logger.error(f"BLE-Client: Setting bottom color failed: {e}")
                await self._disconnect_internal()
                raise

    async def set_both_lights_color(self, ble_device: BLEDevice, top_color_percentage: int, bottom_color_percentage: int) -> None:
        """Sets the color of both lights simultaneously (0-100%, 0=6500K, 100=2700K)."""
        if not 0 <= top_color_percentage <= 100 or not 0 <= bottom_color_percentage <= 100:
            raise ValueError("Color values must be between 0 and 100")

        top_color_value = int(top_color_percentage * 255 / 100)
        bottom_color_value = int(bottom_color_percentage * 255 / 100)

        async with self._connection_lock:
            try:
                client = await self._ensure_connection(ble_device)

                # Read current color values
                current_colors = await client.read_gatt_char(READ_WRITE_LIGHT_COLOR)
                new_colors = bytearray(current_colors)
                if len(new_colors) > max(COLOR_BOTTOM_BYTE, COLOR_TOP_BYTE):
                    new_colors[COLOR_BOTTOM_BYTE] = bottom_color_value
                    new_colors[COLOR_TOP_BYTE] = top_color_value

                await client.write_gatt_char(READ_WRITE_LIGHT_COLOR, bytes(new_colors))

                self.logger.info(f"Both light colors set: top {top_color_percentage}%, bottom {bottom_color_percentage}%")

            except Exception as e:
                self.logger.error(f"BLE-Client: Setting both colors failed: {e}")
                await self._disconnect_internal()
                raise

    # === FAN CONTROL ===

    async def set_fan_level(self, ble_device: BLEDevice, level: int) -> None:
        """Sets the fan level (0=off, 1-3)."""
        self.logger.info(f"BLE-Client: set_fan_level called - Level: {level}, Device: {ble_device.address}")

        if not 0 <= level <= 3:
            raise ValueError("Fan level must be between 0 and 3")

        command_map = {
            0: FanCommands.OFF,
            1: FanCommands.LEVEL_1,
            2: FanCommands.LEVEL_2,
            3: FanCommands.LEVEL_3
        }

        if self._legacy_mode:
            async with self._connection_lock:
                client = await self._ensure_connection(ble_device)
                sender = LegacyCommandSender()
                await sender.fan_level(client, level)
                return
        command = command_map[level]
        self.logger.debug(f"BLE-Client: Fan command generated: {command.hex()}")
        await self._execute_command(ble_device, command)

    # === CONVENIENCE METHODS ===

    async def turn_light_top_on(self, ble_device: BLEDevice) -> None:
        """Turns the top light on."""
        await self.set_light_top_on(ble_device, True)

    async def turn_light_top_off(self, ble_device: BLEDevice) -> None:
        """Turns the top light off."""
        await self.set_light_top_on(ble_device, False)

    async def turn_light_bottom_on(self, ble_device: BLEDevice) -> None:
        """Turns the bottom light on."""
        await self.set_light_bottom_on(ble_device, True)

    async def turn_light_bottom_off(self, ble_device: BLEDevice) -> None:
        """Turns the bottom light off."""
        await self.set_light_bottom_on(ble_device, False)

    async def turn_both_lights_on(self, ble_device: BLEDevice) -> None:
        """Turns both lights on."""
        await self.set_both_lights_on(ble_device, True)

    async def turn_both_lights_off(self, ble_device: BLEDevice) -> None:
        """Turns both lights off."""
        await self.set_both_lights_on(ble_device, False)

    async def turn_fan_off(self, ble_device: BLEDevice) -> None:
        """Turns the fan off."""
        await self.set_fan_level(ble_device, 0)

    # === KELVIN HELPERS ===

    async def set_light_top_color_kelvin(self, ble_device: BLEDevice, kelvin: int) -> None:
        """Sets the color temperature of the top light in Kelvin."""
        if not MIN_KELVIN <= kelvin <= MAX_KELVIN:
            raise ValueError(f"Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}")

        # Convert Kelvin to percentage (2700K = 100%, 6500K = 0%)
        percentage = int(100 * (MAX_KELVIN - kelvin) / (MAX_KELVIN - MIN_KELVIN))
        await self.set_light_top_color(ble_device, percentage)

    async def set_light_bottom_color_kelvin(self, ble_device: BLEDevice, kelvin: int) -> None:
        """Sets the color temperature of the bottom light in Kelvin."""
        if not MIN_KELVIN <= kelvin <= MAX_KELVIN:
            raise ValueError(f"Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}")

        # Convert Kelvin to percentage (2700K = 100%, 6500K = 0%)
        percentage = int(100 * (MAX_KELVIN - kelvin) / (MAX_KELVIN - MIN_KELVIN))
        await self.set_light_bottom_color(ble_device, percentage)

    async def set_both_lights_color_kelvin(self, ble_device: BLEDevice, top_kelvin: int, bottom_kelvin: int) -> None:
        """Sets the color temperature of both lights in Kelvin."""
        if not MIN_KELVIN <= top_kelvin <= MAX_KELVIN:
            raise ValueError(f"Top Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}")
        if not MIN_KELVIN <= bottom_kelvin <= MAX_KELVIN:
            raise ValueError(f"Bottom Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}")

        # Convert Kelvin to percentage
        top_percentage = int(100 * (MAX_KELVIN - top_kelvin) / (MAX_KELVIN - MIN_KELVIN))
        bottom_percentage = int(100 * (MAX_KELVIN - bottom_kelvin) / (MAX_KELVIN - MIN_KELVIN))

        await self.set_both_lights_color(ble_device, top_percentage, bottom_percentage)

    # === CLEANUP ===

    async def disconnect(self):
        """Manually disconnects the connection."""
        await self._disconnect_internal()
