"""Data update coordinator for Berbel integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak import BleakError
from bleak.backends.device import BLEDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady

from .berbel_ble import BerbelBluetoothDeviceData, BerbelDevice
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BerbelDataUpdateCoordinator(DataUpdateCoordinator[BerbelDevice]):
    """Class to manage fetching data from the Berbel device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: BLEDevice,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.ble_device = device
        self.client = BerbelBluetoothDeviceData(_LOGGER)
        self._connection_lock = asyncio.Lock()
        self._immediate_refresh = True  # Controls immediate status updates after commands
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3  # Maximum 3 consecutive failures
        _LOGGER.info("Initializing Berbel coordinator for device %s (%s)", name, device.address)

    async def _async_update_data(self) -> BerbelDevice:
        """Update data via library."""
        _LOGGER.debug("Starting data update for device %s", self.ble_device.address)
        try:
            # Use separate lock for updates to avoid deadlocks
            device_data = await self.client.update_device(self.ble_device)
            _LOGGER.debug("Updated device data: %s", device_data)
            _LOGGER.info("Successfully updated data for %s: Fan=%d, Top Light=%s, Bottom Light=%s", 
                       self.ble_device.address, device_data.fan_level, 
                       device_data.light_top_on, device_data.light_bottom_on)
            
            # Reset failure counter on successful update
            self._consecutive_failures = 0
            return device_data
            
        except BleakError as err:
            self._consecutive_failures += 1
            _LOGGER.warning("BLE connection failed for %s (failure %d/%d): %s", 
                          self.ble_device.address, self._consecutive_failures, 
                          self._max_consecutive_failures, err)
            
            # Only treat as UpdateFailed when too many consecutive failures
            if self._consecutive_failures >= self._max_consecutive_failures:
                _LOGGER.error("Too many consecutive failures for %s, marking as unavailable", 
                            self.ble_device.address)
                raise UpdateFailed(f"Device unavailable after {self._consecutive_failures} failures: {err}") from err
            
            # For few failures: keep old data and warn
            if self.data is not None:
                _LOGGER.warning("Keeping previous data for %s due to temporary BLE error", 
                              self.ble_device.address)
                return self.data
            else:
                raise UpdateFailed(f"Initial connection failed: {err}") from err
                
        except Exception as err:
            self._consecutive_failures += 1
            _LOGGER.exception("Unexpected error fetching device data for %s (failure %d/%d)", 
                            self.ble_device.address, self._consecutive_failures, 
                            self._max_consecutive_failures)
            
            # Only treat as UpdateFailed when too many consecutive failures
            if self._consecutive_failures >= self._max_consecutive_failures:
                _LOGGER.error("Too many consecutive failures for %s, marking as unavailable", 
                            self.ble_device.address)
                raise UpdateFailed(f"Device unavailable after {self._consecutive_failures} failures: {err}") from err
            
            # For few failures: keep old data and warn
            if self.data is not None:
                _LOGGER.warning("Keeping previous data for %s due to temporary error", 
                              self.ble_device.address)
                return self.data
            else:
                raise UpdateFailed(f"Initial connection failed: {err}") from err

    async def _execute_command_optimized(self, command_func, *args, **kwargs) -> None:
        """Executes a command and triggers status update only when needed."""
        try:
            _LOGGER.debug("Coordinator: Executing optimized command...")
            async with self._connection_lock:
                await command_func(*args, **kwargs)
                _LOGGER.debug("Coordinator: Command executed successfully")
            
            # Trigger immediate update only when needed
            if self._immediate_refresh:
                _LOGGER.debug("Coordinator: Triggering immediate update...")
                await self.async_request_refresh()
            else:
                _LOGGER.debug("Coordinator: Skipping immediate update, waiting for next scheduled update")
                
        except BleakError as err:
            _LOGGER.error("Failed to execute command for %s: %s", self.ble_device.address, err)
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error executing command for %s", self.ble_device.address)
            raise

    async def async_set_fan_level(self, level: int) -> None:
        """Set fan level."""
        if not 0 <= level <= 3:
            raise ValueError("Fan level must be between 0 and 3")

        _LOGGER.info("Setting fan level to %d for device %s", level, self.ble_device.address)
        try:
            await self._execute_command_optimized(
                self.client.set_fan_level, self.ble_device, level
            )
            _LOGGER.info("Successfully set fan level to %d", level)
        except Exception as err:
            _LOGGER.error("Failed to set fan level: %s", err)
            raise

    async def async_set_light_brightness(
        self, top_brightness: int | None = None, bottom_brightness: int | None = None
    ) -> None:
        """Set light brightness."""
        if top_brightness is not None and not 0 <= top_brightness <= 100:
            raise ValueError("Top brightness must be between 0 and 100")
        if bottom_brightness is not None and not 0 <= bottom_brightness <= 100:
            raise ValueError("Bottom brightness must be between 0 and 100")

        _LOGGER.info("Setting light brightness - top: %s, bottom: %s for device %s", 
                    top_brightness, bottom_brightness, self.ble_device.address)
        try:
            if top_brightness is not None and bottom_brightness is not None:
                await self._execute_command_optimized(
                    self.client.set_both_lights_brightness, self.ble_device, top_brightness, bottom_brightness
                )
            elif top_brightness is not None:
                await self._execute_command_optimized(
                    self.client.set_light_top_brightness, self.ble_device, top_brightness
                )
            elif bottom_brightness is not None:
                await self._execute_command_optimized(
                    self.client.set_light_bottom_brightness, self.ble_device, bottom_brightness
                )
            
            _LOGGER.info("Successfully set light brightness")
        except Exception as err:
            _LOGGER.error("Failed to set light brightness: %s", err)
            raise

    async def async_set_light_on_off(
        self, top_on: bool | None = None, bottom_on: bool | None = None
    ) -> None:
        """Set light on/off state."""
        _LOGGER.info("Setting light on/off - top: %s, bottom: %s for device %s", 
                    top_on, bottom_on, self.ble_device.address)
        try:
            if top_on is not None and bottom_on is not None:
                if top_on and bottom_on:
                    await self._execute_command_optimized(
                        self.client.turn_both_lights_on, self.ble_device
                    )
                elif not top_on and not bottom_on:
                    await self._execute_command_optimized(
                        self.client.turn_both_lights_off, self.ble_device
                    )
                else:
                    # Mixed state - handle individually
                    if top_on is not None:
                        await self._execute_command_optimized(
                            self.client.set_light_top_on, self.ble_device, top_on
                        )
                    if bottom_on is not None:
                        await self._execute_command_optimized(
                            self.client.set_light_bottom_on, self.ble_device, bottom_on
                        )
            elif top_on is not None:
                await self._execute_command_optimized(
                    self.client.set_light_top_on, self.ble_device, top_on
                )
            elif bottom_on is not None:
                await self._execute_command_optimized(
                    self.client.set_light_bottom_on, self.ble_device, bottom_on
                )
            
            _LOGGER.info("Successfully set light on/off state")
        except Exception as err:
            _LOGGER.error("Failed to set light on/off: %s", err)
            raise

    async def async_set_light_color_temp(
        self, top_kelvin: int | None = None, bottom_kelvin: int | None = None
    ) -> None:
        """Set light color temperature."""
        _LOGGER.info("Setting light color temp - top: %s K, bottom: %s K for device %s", 
                    top_kelvin, bottom_kelvin, self.ble_device.address)
        try:
            if top_kelvin is not None and bottom_kelvin is not None:
                await self._execute_command_optimized(
                    self.client.set_both_lights_color_kelvin, self.ble_device, top_kelvin, bottom_kelvin
                )
            elif top_kelvin is not None:
                await self._execute_command_optimized(
                    self.client.set_light_top_color_kelvin, self.ble_device, top_kelvin
                )
            elif bottom_kelvin is not None:
                await self._execute_command_optimized(
                    self.client.set_light_bottom_color_kelvin, self.ble_device, bottom_kelvin
                )
            
            _LOGGER.info("Successfully set light color temperature")
        except Exception as err:
            _LOGGER.error("Failed to set light color temperature: %s", err)
            raise

    def set_immediate_refresh(self, enabled: bool) -> None:
        """Enables or disables immediate status updates after commands."""
        self._immediate_refresh = enabled
        _LOGGER.info("Immediate refresh %s", "enabled" if enabled else "disabled")

    async def async_cleanup(self) -> None:
        """Cleanup coordinator resources."""
        if hasattr(self.client, 'disconnect'):
            await self.client.disconnect()
        _LOGGER.info("Coordinator cleanup completed") 