"""Config flow for Berbel Skyline Edge Base integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak import BleakError
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .berbel_ble import BerbelBluetoothDeviceData
from .const import DOMAIN, MANUFACTURER, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


class BerbelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Berbel Skyline Edge Base."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        device_name = discovery_info.name or discovery_info.address
        _LOGGER.debug("Discovered Berbel Skyline Edge Base device: %s", device_name)

        # Validate that this is a supported Berbel device
        if not self._is_supported_device(discovery_info):
            return self.async_abort(reason="not_supported")

        self._discovered_device = discovery_info

        # Set the title for the flow
        self.context["title_placeholders"] = {
            "name": device_name,
            "address": discovery_info.address,
        }

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(format_mac(address))
            self._abort_if_unique_id_configured()
            discovery_info = self._discovered_devices[address]

            # Try to connect to the device to validate it's working
            try:
                await self._test_connection(discovery_info)
            except Exception as err:
                _LOGGER.exception("Unexpected exception during connection test")
                return self.async_abort(reason="cannot_connect")

            return self.async_create_entry(
                title=discovery_info.name or discovery_info.address,
                data={
                    CONF_ADDRESS: discovery_info.address,
                    CONF_NAME: discovery_info.name or discovery_info.address,
                },
            )

        # Scan for devices
        current_addresses = self._async_current_addresses()
        for discovery_info in bluetooth.async_discovered_service_info(self.hass):
            if (
                discovery_info.address in current_addresses
                or discovery_info.address in self._discovered_devices
                or not self._is_supported_device(discovery_info)
            ):
                continue
            self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name or 'Unknown'} ({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")

        if self._discovered_device is None:
            return self.async_abort(reason="discovery_error")

        try:
            await self._test_connection(self._discovered_device)
        except Exception as err:
            _LOGGER.exception("Unexpected exception during connection test")
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=self._discovered_device.name or self._discovered_device.address,
            data={
                CONF_ADDRESS: self._discovered_device.address,
                CONF_NAME: self._discovered_device.name or self._discovered_device.address,
            },
        )

    def _async_current_addresses(self) -> set[str]:
        """Return a set of addresses that are already configured."""
        return {
            entry.data[CONF_ADDRESS]
            for entry in self._async_current_entries()
            if CONF_ADDRESS in entry.data
        }

    def _is_supported_device(self, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Check if the discovered device is a supported Berbel device."""
        if discovery_info.name is None:
            return False

        name_upper = discovery_info.name.upper()
        return any(model in name_upper for model in SUPPORTED_MODELS)

    async def _test_connection(self, discovery_info: BluetoothServiceInfoBleak) -> None:
        """Test the connection to the device.
        For legacy models (e.g., HOOD_PER), skip opening a GATT connection here and
        validate based on advertisement data to avoid exhausting BLE slots.
        """
        ble_device = discovery_info.device
        client = BerbelBluetoothDeviceData(_LOGGER)

        # Detect legacy via name/uuids to avoid connecting during config flow
        name_upper = (discovery_info.name or "").upper()
        is_legacy = "HOOD_PER" in name_upper
        if not is_legacy:
            # Try to connect and read basic device info for modern models
            try:
                device = await client.update_device(ble_device)
                _LOGGER.debug("Successfully connected to device: %s", device)
                return
            except BleakError as err:
                _LOGGER.error("BLE connection failed: %s", err)
                raise
            except Exception as err:
                _LOGGER.error("Unexpected error during connection test: %s", err)
                raise
        else:
            # For legacy, ensure we have manufacturer data in the advertisement
            mfd = ble_device.metadata.get("manufacturer_data") if hasattr(ble_device, "metadata") else None
            if isinstance(mfd, dict) and mfd:
                _LOGGER.debug("Legacy device detected; manufacturer data present. Skipping GATT connect test.")
                return
            # If no manufacturer data, we still avoid connecting; log a warning.
            _LOGGER.warning(
                "Legacy device detected but no manufacturer data present in discovery. "
                "Proceeding without active connection test."
            )
            return
