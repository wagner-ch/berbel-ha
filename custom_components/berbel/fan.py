"""Support for Berbel Skyline Edge Base fans."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .coordinator import BerbelDataUpdateCoordinator
from .const import DOMAIN, FAN_SUFFIX, MANUFACTURER, ATTR_FAN_POSTRUN

_LOGGER = logging.getLogger(__name__)

# Fan speed levels (0-3) to percentage mapping
SPEED_RANGE = (1, 3)  # Berbel fan has 3 speed levels


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Berbel Skyline Edge Base fan platform."""
    coordinator: BerbelDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    async_add_entities([BerbelFan(coordinator, config_entry)])


class BerbelFan(CoordinatorEntity[BerbelDataUpdateCoordinator], FanEntity):
    """Representation of a Berbel Skyline Edge Base fan."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_speed_count = 3

    def __init__(
        self,
        coordinator: BerbelDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["address"])},
            "name": config_entry.title or "Berbel Skyline Edge Base",
            "manufacturer": MANUFACTURER,
            "model": "Skyline Edge Base",
            "sw_version": "0.1.0",
        }
        
        self._attr_unique_id = f"{config_entry.data['address']}_fan"
        self._attr_name = f"{config_entry.title or 'Berbel'} {FAN_SUFFIX}"
        
        # Ensure this entity is recognized as a fan
        self._attr_entity_category = None
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.coordinator.data is not None and self.coordinator.data.fan_level > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.coordinator.data is None or self.coordinator.data.fan_level == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self.coordinator.data.fan_level)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        return {
            ATTR_FAN_POSTRUN: self.coordinator.data.fan_postrun_active,
            "fan_level": self.coordinator.data.fan_level,
        }

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            level = 0
        else:
            level = max(1, int(percentage_to_ranged_value(SPEED_RANGE, percentage)))
        
        _LOGGER.debug("Setting fan level to %d (from percentage %d)", level, percentage)
        
        try:
            await self.coordinator.async_set_fan_level(level)
        except Exception as err:
            _LOGGER.error("Error setting fan speed: %s", err)
            raise HomeAssistantError(f"Error setting fan speed: {err}") from err

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            # Default to level 1 when turning on without specific percentage
            level = 1
            _LOGGER.info("Turning on fan with default level 1")
            await self.coordinator.async_set_fan_level(level)
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        _LOGGER.info("Turning off fan")
        await self.coordinator.async_set_fan_level(0)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state() 