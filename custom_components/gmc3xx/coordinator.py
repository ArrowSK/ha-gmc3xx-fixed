"""Data coordinator for the GMC3xx integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BAUD, CONF_RESOLVED_PORT, CONF_SCAN_INTERVAL, CONF_SERIAL_FULL, DEFAULT_SCAN_INTERVAL
from .gmc_protocol import GMCDevice, GMCError, GMCIdentity, GMCSample, candidate_ports

_LOGGER = logging.getLogger(__name__)


class GMCDataUpdateCoordinator(DataUpdateCoordinator[GMCSample]):
    """Keep one persistent serial connection and coordinate polling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name="GMC3xx Radiation Monitor",
            update_interval=timedelta(seconds=int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))),
        )
        self.entry = entry
        self.expected_serial = str(entry.data[CONF_SERIAL_FULL])
        self.preferred_port = str(entry.data[CONF_RESOLVED_PORT])
        self.baud = int(entry.data[CONF_BAUD])
        self.device: GMCDevice | None = None
        self.identity: GMCIdentity | None = None
        self.resolved_port: str | None = None
        self.reconnect_count = 0
        self.successful_updates = 0
        self.last_error: str | None = None

    def _connect_candidate(self, port: str) -> bool:
        device = GMCDevice(port)
        try:
            identity = device.open_and_identify(self.baud)
        except GMCError:
            device.close()
            return False
        if identity.serial_full != self.expected_serial:
            device.close()
            return False
        self.device = device
        self.identity = identity
        self.resolved_port = port
        self.reconnect_count += 1
        return True

    def _ensure_connected(self) -> None:
        if self.device is not None and self.device.connected:
            return
        tried: set[str] = set()
        if self.preferred_port:
            tried.add(self.preferred_port)
            if self._connect_candidate(self.preferred_port):
                return
        for port in candidate_ports():
            if port not in tried and self._connect_candidate(port):
                return
        raise UpdateFailed("Configured GMC counter is not available")

    def _sync_update(self) -> GMCSample:
        self._ensure_connected()
        assert self.device is not None
        try:
            sample = self.device.read_sample()
        except GMCError as err:
            self.last_error = type(err).__name__
            self.device.close()
            self.device = None
            raise UpdateFailed("Lost the GMC serial connection") from err
        self.successful_updates += 1
        self.last_error = None
        return sample

    async def _async_update_data(self) -> GMCSample:
        return await self.hass.async_add_executor_job(self._sync_update)

    async def async_shutdown(self) -> None:
        device, self.device = self.device, None
        if device is not None:
            await self.hass.async_add_executor_job(device.close)
