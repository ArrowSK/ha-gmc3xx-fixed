#!/usr/bin/env python3
import json
import os
import pty
import select
import subprocess
import sys
import threading
import time

BINARY = os.environ.get("GMC320_BINARY", "./gmc320-test")
HEARTBEAT = b"<HEARTBEAT0>>"

IDENTITY = {
    b"<GETVER>>": b"GMC-300Re 4.62",
    b"<GETSERIAL>>": bytes.fromhex("ab 0c 01 23 04 de f0"),
}
CORE_SAMPLE = {
    b"<GETCPM>>": bytes([0x00, 0x12]),
    b"<GETVOLT>>": bytes([40]),
}
DIAG_SAMPLE = {
    b"<GETCPM>>": bytes([0x00, 0x12]),
    b"<GETVOLT>>": bytes([40]),
    b"<GETTEMP>>": bytes([25, 3, 0, 0xAA]),
    b"<GETGYRO>>": bytes([0, 1, 0, 2, 0, 3, 0xAA]),
}


def simulator(master_fd, responses, stop_event):
    """Respond to expected GMC commands, fragmenting each reply byte-by-byte."""
    pending = b""
    commands = [HEARTBEAT] + list(responses.keys())

    while not stop_event.is_set() and commands:
        readable, _, _ = select.select([master_fd], [], [], 3)
        if not readable:
            continue
        chunk = os.read(master_fd, 256)
        if not chunk:
            continue
        pending += chunk

        progressed = True
        while progressed and commands:
            progressed = False
            expected = commands[0]
            idx = pending.find(expected)
            if idx >= 0:
                pending = pending[idx + len(expected):]
                commands.pop(0)
                progressed = True

                if expected == HEARTBEAT:
                    # Simulate stale bytes already in flight when HEARTBEAT0
                    # is accepted. They must be drained before GETCPM.
                    time.sleep(0.10)
                    os.write(master_fd, bytes([0x34, 0x2E]))
                    continue

                for byte in responses[expected]:
                    os.write(master_fd, bytes([byte]))
                    time.sleep(0.015)

    if commands and not stop_event.is_set():
        raise RuntimeError(f"Simulator did not receive expected commands: {commands!r}")


def run_case(args, responses):
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)
    stop_event = threading.Event()
    errors = []

    def worker():
        try:
            simulator(master_fd, responses, stop_event)
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(exc)
            stop_event.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    proc = subprocess.run(
        [BINARY] + [arg.replace("{DEVICE}", slave_name) for arg in args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    stop_event.set()
    thread.join(timeout=2)
    os.close(slave_fd)
    os.close(master_fd)

    if errors:
        raise errors[0]
    if proc.returncode != 0:
        raise AssertionError(
            f"args={args} exited {proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return json.loads(proc.stdout)


def main():
    # Synthetic identity only. No real device identifier belongs in public tests.
    identity = run_case(["--identify", "{DEVICE}", "19200"], IDENTITY)
    assert identity == {
        "version": "GMC-300Re 4.62",
        "serial": "abc1234def0",
        "serial_full": "ab0c012304def0",
        "baud": 19200,
        "has_temp": False,
        "has_gyro": False,
    }, identity

    # 280/300/300E-family core path deliberately does not issue 320-only
    # GETTEMP/GETGYRO commands. Unsupported diagnostic commands were one source
    # of framing risk in older readers.
    core = run_case(["--sample", "{DEVICE}", "19200", "0"], CORE_SAMPLE)
    assert core == {
        "cpm": 18,
        "volt": 4.0,
        "temp": None,
        "x": None,
        "y": None,
        "z": None,
    }, core

    # GMC-320-family path validates documented terminators and big-endian fields.
    diag = run_case(["--sample", "{DEVICE}", "57600", "1"], DIAG_SAMPLE)
    assert diag == {
        "cpm": 18,
        "volt": 4.0,
        "temp": 25.3,
        "x": 1,
        "y": 2,
        "z": 3,
    }, diag

    # A correctly framed high 16-bit value must pass unchanged. The safety fix
    # is transport validation, never an arbitrary numerical ceiling.
    high = dict(CORE_SAMPLE)
    high[b"<GETCPM>>"] = bytes([0xC5, 0x74])
    high_sample = run_case(["--sample", "{DEVICE}", "115200", "0"], high)
    assert high_sample["cpm"] == 50548, high_sample

    # An unsupported user-supplied baud must fail closed.
    proc = subprocess.run(
        [BINARY, "--identify", "/dev/null", "12345"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode != 0

    print("protocol tests passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TEST FAILURE: {exc}", file=sys.stderr)
        raise
