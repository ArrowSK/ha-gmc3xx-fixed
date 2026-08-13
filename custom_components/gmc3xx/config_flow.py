"""Config flow for GMC3xx Radiation Monitor."""

from __future__ import annotations

from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APP_STOPPED, CONF_BAUD, CONF_HAS_DIAGNOSTICS, CONF_RESOLVED_PORT,
    CONF_SCAN_INTERVAL, CONF_SERIAL_COMPAT, CONF_SERIAL_FULL, CONF_VERSION,
    DEFAULT_BAUD, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL, SUPPORTED_BAUDS,
)
from .gmc_protocol import (
    GMCAmbiguousDeviceError, GMCError, GMCIdentity, GMCNotFoundError,
    discover_compatible_devices, probe_port,
)

CONF_PORT = "port"


def _probe(port: str, baud: str) -> GMCIdentity:
    if port == DEFAULT_PORT:
        matches = discover_compatible_devices(baud)
        if not matches:
            raise GMCNotFoundError("No compatible GMC counter was found")
        if len(matches) > 1:
            raise GMCAmbiguousDeviceError("More than one compatible GMC counter was found")
        return matches[0]
    return probe_port(port, baud)


async def _async_probe(hass: HomeAssistant, port: str, baud: str) -> GMCIdentity:
    return await hass.async_add_executor_job(_probe, port, baud)


class GMC3xxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_APP_STOPPED]:
                errors["base"] = "app_must_be_stopped"
            else:
                port = str(user_input[CONF_PORT]).strip()
                baud = str(user_input[CONF_BAUD])
                try:
                    identity = await _async_probe(self.hass, port, baud)
                except GMCAmbiguousDeviceError:
                    errors["base"] = "multiple_devices"
                except GMCNotFoundError:
                    errors["base"] = "device_not_found"
                except GMCError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(identity.serial_full)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=identity.version,
                        data={
                            CONF_RESOLVED_PORT: identity.port,
                            CONF_BAUD: identity.baud,
                            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                            CONF_SERIAL_FULL: identity.serial_full,
                            CONF_SERIAL_COMPAT: identity.serial_compat,
                            CONF_VERSION: identity.version,
                            CONF_HAS_DIAGNOSTICS: identity.has_320_diagnostics,
                        },
                    )
        baud_choices = [DEFAULT_BAUD, *[str(value) for value in SUPPORTED_BAUDS]]
        schema = vol.Schema({
            vol.Required(CONF_APP_STOPPED, default=False): bool,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
            vol.Required(CONF_BAUD, default=DEFAULT_BAUD): vol.In(baud_choices),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
