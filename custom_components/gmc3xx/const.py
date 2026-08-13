"""Constants for the GMC3xx integration."""

from __future__ import annotations

DOMAIN = "gmc3xx"
PLATFORMS = ["sensor"]

CONF_APP_STOPPED = "app_stopped"
CONF_BAUD = "baud"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SERIAL_FULL = "serial_full"
CONF_SERIAL_COMPAT = "serial_compat"
CONF_VERSION = "version"
CONF_HAS_DIAGNOSTICS = "has_diagnostics"
CONF_RESOLVED_PORT = "resolved_port"

DEFAULT_PORT = "auto"
DEFAULT_BAUD = "auto"
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 3600

SUPPORTED_BAUDS = (
    115200,
    57600,
    19200,
    38400,
    9600,
    4800,
    2400,
    1200,
    14400,
    28800,
)
