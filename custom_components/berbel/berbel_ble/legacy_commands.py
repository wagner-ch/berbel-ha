"""Legacy command sender for older Berbel models.

Builds URL-encoded ASCII commands with PIN prefix and writes to RX characteristic.
"""
from __future__ import annotations
import asyncio
import logging
import urllib.parse
from typing import Optional
from bleak import BleakClient

from .const import (
    LEGACY_UUID_RX,
    LEGACY_UUID_RX_2018,
    LEGACY_DEFAULT_PIN,
)

_LOGGER = logging.getLogger(__name__)


class LegacyCommandSender:
    """Helper to send commands to legacy devices via RX characteristic.

    This implements a minimal subset of commands needed for basic control.
    """

    def __init__(self, pin: str | None = None):
        self.pin = pin or LEGACY_DEFAULT_PIN

    @staticmethod
    def _rx_uuid_for_device(client: BleakClient) -> str:
        # Try 2018 first as it is more recent, fall back to legacy
        services = [s.uuid.lower() for s in client.services]
        if LEGACY_UUID_RX_2018.lower() in services:
            return LEGACY_UUID_RX_2018
        return LEGACY_UUID_RX

    def _encode(self, command: str) -> bytes:
        # Concatenate PIN and command text then URL-encode as in the app
        s = f"{self.pin}{command}"
        return urllib.parse.quote(s, safe="").encode("utf-8")

    async def send(self, client: BleakClient, command: str) -> None:
        uuid = self._rx_uuid_for_device(client)
        payload = self._encode(command)
        _LOGGER.debug("Legacy RX write: uuid=%s, payload=%s", uuid, payload)
        await client.write_gatt_char(uuid, payload, response=True)

    # High-level mappings (string values taken from decompiled R.java identifiers)
    # We do not know exact string content; the device only needs the identifier text.
    async def fan_off(self, client: BleakClient):
        await self.send(client, "cmd_off")

    async def fan_level(self, client: BleakClient, level: int):
        if level <= 0:
            await self.fan_off(client)
        elif level == 1:
            await self.send(client, "cmd_luft1")
        elif level == 2:
            await self.send(client, "cmd_luft2")
        else:
            await self.send(client, "cmd_luft3")

    async def lights_on(self, client: BleakClient):
        # 'cmd_panel_on' is used in the app to toggle lighting panel
        await self.send(client, "cmd_panel_on")

    async def lights_off(self, client: BleakClient):
        await self.send(client, "cmd_panel_off")

    async def postrun_toggle(self, client: BleakClient):
        await self.send(client, "cmd_nachlauf")

    async def postrun_off(self, client: BleakClient):
        await self.send(client, "cmd_nachlauf_aus")
