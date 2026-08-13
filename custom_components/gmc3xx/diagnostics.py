"""Diagnostics support for GMC3xx Radiation Monitor."""

from __future__ import annotations
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import GMCDataUpdateCoordinator


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics without exposing serial numbers or device paths."""
    coordinator: GMCDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    identity = coordinator.identity
    return {
        "integration": {
            "version": identity.version if identity else entry.title,
            "baud": coordinator.baud,
            "poll_interval_seconds": int(coordinator.update_interval.total_seconds()),
            "has_320_diagnostics": bool(identity and identity.has_320_diagnostics),
        },
        "runtime": {
            "connected": bool(coordinator.device and coordinator.device.connected),
            "successful_updates": coordinator.successful_updates,
            "reconnect_count": coordinator.reconnect_count,
            "last_error_type": coordinator.last_error,
            "last_update_success": coordinator.last_update_success,
        },
    }
