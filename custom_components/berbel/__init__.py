"""The Berbel integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .coordinator import BerbelDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT, Platform.BINARY_SENSOR]

# Service schemas
SERVICE_SET_IMMEDIATE_REFRESH_SCHEMA = vol.Schema({
    vol.Required("enabled"): cv.boolean,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Berbel from a config entry."""
    address = entry.data[CONF_ADDRESS]
    
    # Get the Bluetooth device
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Berbel device with address {address}"
        )

    # Create the coordinator
    coordinator = BerbelDataUpdateCoordinator(
        hass, ble_device, entry.title or "Berbel"
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_set_immediate_refresh(call: ServiceCall) -> None:
        """Handle set_immediate_refresh service call."""
        enabled = call.data["enabled"]
        # Apply to all coordinators
        for coordinator in hass.data[DOMAIN].values():
            if isinstance(coordinator, BerbelDataUpdateCoordinator):
                coordinator.set_immediate_refresh(enabled)
        _LOGGER.info("Set immediate refresh to %s for all Berbel devices", enabled)

    async def handle_disconnect_ble(call: ServiceCall) -> None:
        """Handle disconnect_ble service call."""
        # Disconnect all coordinators
        for coordinator in hass.data[DOMAIN].values():
            if isinstance(coordinator, BerbelDataUpdateCoordinator):
                await coordinator.client.disconnect()
        _LOGGER.info("Disconnected BLE for all Berbel devices")

    # Register services only once
    if not hass.services.has_service(DOMAIN, "set_immediate_refresh"):
        hass.services.async_register(
            DOMAIN,
            "set_immediate_refresh",
            handle_set_immediate_refresh,
            schema=SERVICE_SET_IMMEDIATE_REFRESH_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, "disconnect_ble"):
        hass.services.async_register(
            DOMAIN,
            "disconnect_ble",
            handle_disconnect_ble,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Get the coordinator
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Clean up the coordinator and BLE connection
    await coordinator.async_cleanup()
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove services if no more entries
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "set_immediate_refresh")
        hass.services.async_remove(DOMAIN, "disconnect_ble")

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        # No migration needed for version 1
        pass

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True 