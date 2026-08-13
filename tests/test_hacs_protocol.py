#!/usr/bin/env python3
"""Regression tests for the pure-Python HACS protocol implementation."""

from __future__ import annotations
from collections import defaultdict
import importlib.util
from pathlib import Path
import sys
import types

serial_stub = types.ModuleType("serial")
serial_stub.EIGHTBITS = 8
serial_stub.PARITY_NONE = "N"
serial_stub.STOPBITS_ONE = 1
class SerialException(Exception):
    pass
serial_stub.SerialException = SerialException
serial_stub.Serial = object
sys.modules.setdefault("serial", serial_stub)

pkg = types.ModuleType("custom_components")
pkg.__path__ = []
sys.modules.setdefault("custom_components", pkg)
pkg2 = types.ModuleType("custom_components.gmc3xx")
pkg2.__path__ = [str(Path("custom_components/gmc3xx").resolve())]
sys.modules.setdefault("custom_components.gmc3xx", pkg2)

for name in ("const", "gmc_protocol"):
    path = Path(f"custom_components/gmc3xx/{name}.py")
    spec = importlib.util.spec_from_file_location(f"custom_components.gmc3xx.{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
protocol = sys.modules["custom_components.gmc3xx.gmc_protocol"]


class FakeSerial:
    instances = []
    response_map = {
        b"<GETVER>>": b"GMC-300Re 4.62",
        b"<GETSERIAL>>": bytes.fromhex("ab 0c 01 23 04 de f0"),
        b"<GETCPM>>": bytes([0x00, 0x12]),
        b"<GETVOLT>>": bytes([40]),
    }
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.timeout = kwargs.get("timeout")
        self.pending = bytearray()
        self.closed = False
        self.commands = defaultdict(int)
        FakeSerial.instances.append(self)
    def close(self): self.closed = True
    def flush(self): return None
    def reset_input_buffer(self): self.pending.clear()
    def write(self, data):
        self.commands[bytes(data)] += 1
        if data == b"<HEARTBEAT0>>": self.pending.extend(b"4.")
        elif data in self.response_map: self.pending.extend(self.response_map[data])
        return len(data)
    def read(self, size=1):
        if not self.pending: return b""
        value = bytes(self.pending[:1])
        del self.pending[:1]
        return value


def make_device(responses=None):
    class Instance(FakeSerial):
        response_map = responses or FakeSerial.response_map
    return protocol.GMCDevice("/dev/fake", serial_factory=Instance)


def main():
    protocol.GMC_HEARTBEAT_SETTLE = 0
    protocol.GMC_INTER_COMMAND = 0
    protocol.GMC_TIMEOUT = 0.002
    protocol.GMC_IDENTIFY_TIMEOUT = 0.002
    protocol.time.sleep = lambda _seconds: None

    device = make_device()
    identity = device.open_and_identify(19200)
    assert identity.version == "GMC-300Re 4.62"
    assert identity.serial_compat == "abc1234def0"
    assert identity.serial_full == "ab0c012304def0"
    assert not identity.has_320_diagnostics
    sample = device.read_sample()
    assert sample.cpm == 18 and sample.volt == 4.0 and sample.temp is None
    assert device.connected
    device.close()

    responses = dict(FakeSerial.response_map)
    responses[b"<GETCPM>>"] = bytes([0xC5, 0x74])
    device = make_device(responses)
    device.open_and_identify(19200)
    assert device.read_sample().cpm == 50548
    device.close()

    responses = dict(FakeSerial.response_map)
    responses[b"<GETVER>>"] = b"GMC-320 V4.123"
    responses[b"<GETTEMP>>"] = bytes([25, 3, 0, 0xAA])
    responses[b"<GETGYRO>>"] = bytes([0, 1, 0, 2, 0, 3, 0xAA])
    device = make_device(responses)
    assert device.open_and_identify(19200).has_320_diagnostics
    sample = device.read_sample()
    assert (sample.temp, sample.x, sample.y, sample.z) == (25.3, 1, 2, 3)
    device.close()

    responses = dict(FakeSerial.response_map)
    responses[b"<GETCPM>>"] = bytes([0x12])
    device = make_device(responses)
    device.open_and_identify(19200)
    try:
        device.read_sample()
    except protocol.GMCProtocolError:
        pass
    else:
        raise AssertionError("incomplete CPM reply was accepted")
    device.close()
    print("HACS protocol tests passed")


if __name__ == "__main__":
    main()
