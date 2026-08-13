"""RFC1201 serial protocol support for older GQ GMC counters.

The behavior intentionally mirrors the proven reader used by the companion
Home Assistant App in this repository: complete-length reads, stale-input
flushing, bounded retries, a persistent open port, and model-aware diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from glob import glob
import logging
import os
import time
from typing import Protocol

import serial

from .const import SUPPORTED_BAUDS

_LOGGER = logging.getLogger(__name__)

GMC_TIMEOUT = 1.8
GMC_IDENTIFY_TIMEOUT = 0.9
GMC_RETRIES = 3
GMC_INTER_COMMAND = 0.025
GMC_HEARTBEAT_SETTLE = 0.5


class GMCError(Exception):
    """Base exception for GMC protocol failures."""


class GMCConnectionError(GMCError):
    """Raised when the serial device cannot be opened or read."""


class GMCProtocolError(GMCError):
    """Raised when the counter returns an incomplete or invalid reply."""


class GMCNotFoundError(GMCError):
    """Raised when no compatible counter is found."""


class GMCAmbiguousDeviceError(GMCError):
    """Raised when more than one compatible counter is found."""


@dataclass(frozen=True, slots=True)
class GMCIdentity:
    """Stable identity reported by the counter."""

    version: str
    serial_compat: str
    serial_full: str
    baud: int
    has_320_diagnostics: bool
    port: str


@dataclass(frozen=True, slots=True)
class GMCSample:
    """One complete sample from the counter."""

    cpm: int
    volt: float
    temp: float | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None


class _SerialLike(Protocol):
    timeout: float | None
    def close(self) -> None: ...
    def flush(self) -> None: ...
    def read(self, size: int = 1) -> bytes: ...
    def reset_input_buffer(self) -> None: ...
    def write(self, data: bytes) -> int: ...


def _format_serial_compat(raw: bytes) -> str:
    return "".join(f"{value:x}" for value in raw)


def _format_serial_full(raw: bytes) -> str:
    return "".join(f"{value:02x}" for value in raw)


def _sanitize_ascii(raw: bytes) -> str:
    return "".join(chr(value) if 0x20 <= value <= 0x7E else "?" for value in raw)


def _valid_rfc1201_version(version: str) -> bool:
    return version.startswith("GMC-") and len(version) >= 8


def _model_has_320_diagnostics(version: str) -> bool:
    return version.startswith("GMC-320")


def _decode_be16(raw: bytes) -> int:
    return (raw[0] << 8) | raw[1]


def candidate_ports() -> list[str]:
    """Return unique serial candidates in the same order as the App."""
    candidates: list[str] = []
    seen_real: set[str] = set()
    for pattern in ("/dev/serial/by-id/*", "/dev/ttyUSB*", "/dev/ttyACM*"):
        for candidate in sorted(glob(pattern)):
            if not os.path.exists(candidate):
                continue
            real = os.path.realpath(candidate)
            if real in seen_real:
                continue
            seen_real.add(real)
            candidates.append(candidate)
    return candidates


class GMCDevice:
    """Persistent RFC1201 serial connection to one GMC counter."""

    def __init__(self, port: str, serial_factory=None) -> None:
        self.port = port
        self._serial_factory = serial_factory or serial.Serial
        self._serial: _SerialLike | None = None
        self.identity: GMCIdentity | None = None

    @property
    def connected(self) -> bool:
        return self._serial is not None

    def close(self) -> None:
        serial_obj, self._serial = self._serial, None
        if serial_obj is not None:
            try:
                serial_obj.close()
            except Exception:
                _LOGGER.debug("Error while closing GMC serial port", exc_info=True)

    def _open_serial(self, baud: int) -> None:
        if baud not in SUPPORTED_BAUDS:
            raise GMCConnectionError(f"Unsupported baud rate: {baud}")
        self.close()
        kwargs = dict(
            port=self.port, baudrate=baud, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
            timeout=0.10, write_timeout=2.0, xonxoff=False, rtscts=False, dsrdtr=False,
        )
        try:
            try:
                serial_obj = self._serial_factory(**kwargs, exclusive=True)
            except TypeError:
                serial_obj = self._serial_factory(**kwargs)
        except (OSError, serial.SerialException) as err:
            raise GMCConnectionError("Unable to open the serial device") from err
        self._serial = serial_obj
        try:
            self._flush_input()
            self._write_all(b"<HEARTBEAT0>>")
            serial_obj.flush()
            time.sleep(GMC_HEARTBEAT_SETTLE)
            self._flush_input()
        except Exception:
            self.close()
            raise

    def _flush_input(self) -> None:
        if self._serial is None:
            raise GMCConnectionError("Serial device is not open")
        try:
            self._serial.reset_input_buffer()
        except (OSError, serial.SerialException) as err:
            raise GMCConnectionError("Unable to flush the serial input buffer") from err

    def _write_all(self, payload: bytes) -> None:
        if self._serial is None:
            raise GMCConnectionError("Serial device is not open")
        offset = 0
        try:
            while offset < len(payload):
                written = self._serial.write(payload[offset:])
                if written is None or written <= 0:
                    raise GMCConnectionError("Serial write returned no data")
                offset += written
        except (OSError, serial.SerialException) as err:
            raise GMCConnectionError("Serial write failed") from err

    def _read_exact(self, length: int, timeout: float) -> bytes:
        if self._serial is None:
            raise GMCConnectionError("Serial device is not open")
        deadline = time.monotonic() + timeout
        chunks = bytearray()
        try:
            while len(chunks) < length:
                if time.monotonic() >= deadline:
                    break
                chunk = self._serial.read(length - len(chunks))
                if chunk:
                    chunks.extend(chunk)
        except (OSError, serial.SerialException) as err:
            raise GMCConnectionError("Serial read failed") from err
        if len(chunks) != length:
            raise GMCProtocolError(
                f"Incomplete serial reply: expected {length} bytes, received {len(chunks)}"
            )
        return bytes(chunks)

    def _transact_exact(self, command: bytes, reply_length: int, *, timeout: float = GMC_TIMEOUT,
                        retries: int = GMC_RETRIES, quiet: bool = False) -> bytes:
        last_error: GMCError | None = None
        for attempt in range(1, retries + 1):
            try:
                self._flush_input()
                time.sleep(GMC_INTER_COMMAND)
                self._flush_input()
                self._write_all(command)
                assert self._serial is not None
                self._serial.flush()
                return self._read_exact(reply_length, timeout)
            except GMCError as err:
                last_error = err
                if not quiet and attempt < retries:
                    _LOGGER.debug("Incomplete response for GMC command; retrying (%s/%s)", attempt, retries)
                time.sleep(0.05)
        raise GMCProtocolError("Failed to obtain a complete GMC serial response") from last_error

    def _identity_on_open_port(self, baud: int, *, quick: bool) -> GMCIdentity:
        version_raw = self._transact_exact(
            b"<GETVER>>", 14,
            timeout=GMC_IDENTIFY_TIMEOUT if quick else GMC_TIMEOUT,
            retries=1 if quick else GMC_RETRIES, quiet=quick,
        )
        version = _sanitize_ascii(version_raw)
        if not _valid_rfc1201_version(version):
            raise GMCProtocolError("Device did not return an RFC1201 GMC identity")
        serial_raw = self._transact_exact(b"<GETSERIAL>>", 7)
        serial_compat = _format_serial_compat(serial_raw)
        serial_full = _format_serial_full(serial_raw)
        if not serial_compat or not serial_full:
            raise GMCProtocolError("Device returned an empty serial identity")
        identity = GMCIdentity(
            version=version, serial_compat=serial_compat, serial_full=serial_full, baud=baud,
            has_320_diagnostics=_model_has_320_diagnostics(version), port=self.port,
        )
        self.identity = identity
        return identity

    def open_and_identify(self, baud: str | int = "auto") -> GMCIdentity:
        if baud != "auto":
            try:
                baud_int = int(baud)
            except (TypeError, ValueError) as err:
                raise GMCConnectionError(f"Invalid baud setting: {baud}") from err
            if baud_int not in SUPPORTED_BAUDS:
                raise GMCConnectionError(f"Unsupported baud rate: {baud_int}")
            self._open_serial(baud_int)
            try:
                return self._identity_on_open_port(baud_int, quick=False)
            except GMCError:
                self.close()
                raise
        last_error: GMCError | None = None
        for baud_int in SUPPORTED_BAUDS:
            try:
                self._open_serial(baud_int)
                return self._identity_on_open_port(baud_int, quick=True)
            except GMCError as err:
                last_error = err
                self.close()
        raise GMCNotFoundError(
            "No RFC1201-compatible GMC identity found at supported baud rates"
        ) from last_error

    def read_sample(self) -> GMCSample:
        if self.identity is None or self._serial is None:
            raise GMCConnectionError("GMC device is not identified")
        cpm_raw = self._transact_exact(b"<GETCPM>>", 2)
        volt_raw = self._transact_exact(b"<GETVOLT>>", 1)
        cpm = _decode_be16(cpm_raw)
        volt = volt_raw[0] / 10.0
        if not self.identity.has_320_diagnostics:
            return GMCSample(cpm=cpm, volt=volt)
        temp_raw = self._transact_exact(b"<GETTEMP>>", 4)
        if temp_raw[3] != 0xAA:
            raise GMCProtocolError("Invalid GETTEMP terminator")
        gyro_raw = self._transact_exact(b"<GETGYRO>>", 7)
        if gyro_raw[6] != 0xAA:
            raise GMCProtocolError("Invalid GETGYRO terminator")
        temp = temp_raw[0] + temp_raw[1] / 10.0
        if temp_raw[2] != 0:
            temp = -temp
        return GMCSample(
            cpm=cpm, volt=volt, temp=temp,
            x=_decode_be16(gyro_raw[0:2]), y=_decode_be16(gyro_raw[2:4]), z=_decode_be16(gyro_raw[4:6]),
        )


def probe_port(port: str, baud: str | int = "auto") -> GMCIdentity:
    device = GMCDevice(port)
    try:
        return device.open_and_identify(baud)
    finally:
        device.close()


def discover_compatible_devices(baud: str | int = "auto") -> list[GMCIdentity]:
    matches: list[GMCIdentity] = []
    for port in candidate_ports():
        try:
            matches.append(probe_port(port, baud))
        except GMCError:
            continue
    return matches
