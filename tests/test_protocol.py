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


class Simulator:
    def __init__(self, master_fd, responses, heartbeat_tail=b"\x34\x2e"):
        self.master_fd = master_fd
        self.responses = responses
        self.heartbeat_tail = heartbeat_tail
        self.stop_event = threading.Event()
        self.error = None
        self.heartbeat_count = 0
        self.command_counts = {}
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)
        if self.error:
            raise self.error

    def _reply_fragmented(self, payload):
        for byte in payload:
            if self.stop_event.is_set():
                return
            os.write(self.master_fd, bytes([byte]))
            time.sleep(0.015)

    def _run(self):
        pending = b""
        commands = [HEARTBEAT] + list(self.responses.keys())
        try:
            while not self.stop_event.is_set():
                readable, _, _ = select.select([self.master_fd], [], [], 0.25)
                if not readable:
                    continue
                chunk = os.read(self.master_fd, 256)
                if not chunk:
                    continue
                pending += chunk

                progressed = True
                while progressed:
                    progressed = False
                    best = None
                    best_idx = None
                    for command in commands:
                        idx = pending.find(command)
                        if idx >= 0 and (best_idx is None or idx < best_idx):
                            best = command
                            best_idx = idx
                    if best is None:
                        if len(pending) > 512:
                            pending = pending[-128:]
                        continue

                    pending = pending[best_idx + len(best):]
                    progressed = True
                    self.command_counts[best] = self.command_counts.get(best, 0) + 1

                    if best == HEARTBEAT:
                        self.heartbeat_count += 1
                        if self.heartbeat_tail:
                            time.sleep(0.10)
                            self._reply_fragmented(self.heartbeat_tail)
                    else:
                        self._reply_fragmented(self.responses[best])
        except (OSError, ValueError) as exc:
            if not self.stop_event.is_set():
                self.error = exc
                self.stop_event.set()


def make_pty(responses):
    master_fd, slave_fd = pty.openpty()
    simulator = Simulator(master_fd, responses)
    simulator.start()
    return master_fd, slave_fd, os.ttyname(slave_fd), simulator


def cleanup(master_fd, slave_fd, simulator):
    simulator.stop_event.set()
    simulator.thread.join(timeout=2)
    os.close(slave_fd)
    os.close(master_fd)
    if simulator.error:
        raise simulator.error


def run_case(args, responses):
    master_fd, slave_fd, slave_name, simulator = make_pty(responses)
    try:
        proc = subprocess.run(
            [BINARY] + [arg.replace("{DEVICE}", slave_name) for arg in args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"args={args} exited {proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
            )
        return json.loads(proc.stdout), simulator
    finally:
        cleanup(master_fd, slave_fd, simulator)


def run_stream_two_samples(responses):
    master_fd, slave_fd, slave_name, simulator = make_pty(responses)
    proc = None
    try:
        proc = subprocess.Popen(
            [BINARY, "--stream", slave_name, "19200", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        lines = []
        deadline = time.monotonic() + 10
        while len(lines) < 3 and time.monotonic() < deadline:
            line = proc.stdout.readline()
            if line:
                lines.append(json.loads(line))
            elif proc.poll() is not None:
                break
        if len(lines) != 3:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise AssertionError(f"stream produced {len(lines)} lines: {lines!r}\nstderr={stderr}")
        return lines, simulator.heartbeat_count
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        cleanup(master_fd, slave_fd, simulator)


def main():
    responses = {**IDENTITY, **CORE_SAMPLE}

    identity, _ = run_case(["--identify", "{DEVICE}", "19200"], responses)
    assert identity == {
        "version": "GMC-300Re 4.62",
        "serial": "abc1234def0",
        "serial_full": "ab0c012304def0",
        "baud": 19200,
        "has_temp": False,
        "has_gyro": False,
    }, identity

    core, _ = run_case(["--sample", "{DEVICE}", "19200", "0"], CORE_SAMPLE)
    assert core == {
        "cpm": 18,
        "volt": 4.0,
        "temp": None,
        "x": None,
        "y": None,
        "z": None,
    }, core

    diag, _ = run_case(["--sample", "{DEVICE}", "57600", "1"], DIAG_SAMPLE)
    assert diag == {
        "cpm": 18,
        "volt": 4.0,
        "temp": 25.3,
        "x": 1,
        "y": 2,
        "z": 3,
    }, diag

    high = dict(CORE_SAMPLE)
    high[b"<GETCPM>>"] = bytes([0xC5, 0x74])
    high_sample, _ = run_case(["--sample", "{DEVICE}", "115200", "0"], high)
    assert high_sample["cpm"] == 50548, high_sample

    stream_lines, heartbeat_count = run_stream_two_samples(responses)
    assert stream_lines[0]["type"] == "identity", stream_lines
    assert stream_lines[1]["type"] == "sample", stream_lines
    assert stream_lines[2]["type"] == "sample", stream_lines
    assert stream_lines[1]["cpm"] == 18 and stream_lines[2]["cpm"] == 18, stream_lines
    assert heartbeat_count == 1, f"persistent stream reopened serial port: heartbeat_count={heartbeat_count}"

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
