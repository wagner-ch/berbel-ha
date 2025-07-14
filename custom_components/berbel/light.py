"""Support for Berbel Skyline Edge Base lights."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .coordinator import BerbelDataUpdateCoordinator
from .const import (
    DOMAIN,
    LIGHT_TOP_SUFFIX,
    LIGHT_BOTTOM_SUFFIX,
    MANUFACTURER,
    ATTR_COLOR_TEMP_KELVIN,
)
from .berbel_ble.const import MIN_KELVIN, MAX_KELVIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Berbel Skyline Edge Base light platform."""
    coordinator: BerbelDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    async_add_entities([
        BerbelLight(coordinator, config_entry, "top"),
        BerbelLight(coordinator, config_entry, "bottom"),
    ])


class BerbelLight(CoordinatorEntity[BerbelDataUpdateCoordinator], LightEntity):
    """Representation of a Berbel Skyline Edge Base light."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_mireds = color_temperature_kelvin_to_mired(MAX_KELVIN)
    _attr_max_mireds = color_temperature_kelvin_to_mired(MIN_KELVIN)

    def __init__(
        self,
        coordinator: BerbelDataUpdateCoordinator,
        config_entry: ConfigEntry,
        position: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        
        self.position = position
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["address"])},
            "name": config_entry.title or "Berbel Skyline Edge Base",
            "manufacturer": MANUFACTURER,
            "model": "Skyline Edge Base",
            "sw_version": "0.1.0",
        }
        
        position_suffix = LIGHT_TOP_SUFFIX if position == "top" else LIGHT_BOTTOM_SUFFIX
        self._attr_unique_id = f"{config_entry.data['address']}_light_{position}"
        self._attr_name = f"{config_entry.title or 'Berbel'} {position_suffix}"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if self.position == "top":
            return self.coordinator.data.light_top_on
        return self.coordinator.data.light_bottom_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self.position == "top":
            brightness_percent = self.coordinator.data.light_top_brightness
        else:
            brightness_percent = self.coordinator.data.light_bottom_brightness
        
        # Convert from 0-100% to 0-255
        return int(brightness_percent * 255 / 100) if brightness_percent > 0 else 0

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        if self.position == "top":
            kelvin = self.coordinator.data.light_top_color_kelvin
        else:
            kelvin = self.coordinator.data.light_bottom_color_kelvin
        
        return color_temperature_kelvin_to_mired(kelvin)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.position == "top":
            kelvin = self.coordinator.data.light_top_color_kelvin
            brightness = self.coordinator.data.light_top_brightness
        else:
            kelvin = self.coordinator.data.light_bottom_color_kelvin
            brightness = self.coordinator.data.light_bottom_brightness

        return {
            ATTR_COLOR_TEMP_KELVIN: kelvin,
            "brightness_percent": brightness,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        
        try:
            # Handle brightness
            brightness_percent = None
            if brightness is not None:
                # Convert from 0-255 to 0-100%
                brightness_percent = int(brightness * 100 / 255)
            elif not self.is_on:
                # If light is off and no brightness specified, use 100%
                brightness_percent = 100

            # Handle color temperature
            kelvin = None
            if color_temp is not None:
                kelvin = color_temperature_mired_to_kelvin(color_temp)

            # Set brightness first if specified
            if brightness_percent is not None:
                if self.position == "top":
                    await self.coordinator.async_set_light_brightness(
                        top_brightness=brightness_percent
                    )
                else:
                    await self.coordinator.async_set_light_brightness(
                        bottom_brightness=brightness_percent
                    )

            # Set color temperature if specified
            if kelvin is not None:
                if self.position == "top":
                    await self.coordinator.async_set_light_color_temp(top_kelvin=kelvin)
                else:
                    await self.coordinator.async_set_light_color_temp(bottom_kelvin=kelvin)

            # If only turning on without specific brightness, just turn on
            if brightness_percent is None and color_temp is None:
                if self.position == "top":
                    await self.coordinator.async_set_light_on_off(top_on=True)
                else:
                    await self.coordinator.async_set_light_on_off(bottom_on=True)

        except Exception as err:
            _LOGGER.error("Error turning on %s light: %s", self.position, err)
            raise HomeAssistantError(
                f"Error turning on {self.position} light: {err}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        try:
            if self.position == "top":
                await self.coordinator.async_set_light_on_off(top_on=False)
            else:
                await self.coordinator.async_set_light_on_off(bottom_on=False)
        except Exception as err:
            _LOGGER.error("Error turning off %s light: %s", self.position, err)
            raise HomeAssistantError(
                f"Error turning off {self.position} light: {err}"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state() 