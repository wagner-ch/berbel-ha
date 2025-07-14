"""Support for Berbel Skyline Edge Base binary sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BerbelDataUpdateCoordinator
from .const import DOMAIN, SWITCH_POSTRUN_SUFFIX, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Berbel Skyline Edge Base binary sensor platform."""
    coordinator: BerbelDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    async_add_entities([BerbelPostrunBinarySensor(coordinator, config_entry)])


class BerbelPostrunBinarySensor(CoordinatorEntity[BerbelDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a Berbel Skyline Edge Base postrun binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: BerbelDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["address"])},
            "name": config_entry.title or "Berbel Skyline Edge Base",
            "manufacturer": MANUFACTURER,
            "model": "Skyline Edge Base",
            "sw_version": "0.1.0",
        }
        
        self._attr_unique_id = f"{config_entry.data['address']}_postrun"
        self._attr_name = f"{config_entry.title or 'Berbel'} {SWITCH_POSTRUN_SUFFIX}"
        self._attr_icon = "mdi:fan-clock"
        self._attr_entity_category = None
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return true if the postrun is active."""
        return self.coordinator.data is not None and self.coordinator.data.fan_postrun_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        return {
            "fan_level": self.coordinator.data.fan_level,
            "description": "Zeigt an, ob der Lüfter-Nachlauf aktiv ist",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state() 