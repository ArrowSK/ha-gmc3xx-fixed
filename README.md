# GMC3xx Fixed for Home Assistant

A Home Assistant app (formerly called an add-on) that reads GQ GMC Geiger counters using the legacy **GQ-RFC1201** serial protocol and publishes measurements to MQTT.

This repository is a compatibility fork of [`gi1mic/gmc320`](https://github.com/gi1mic/gmc320). It preserves the original MQTT topic/payload contract where practical while fixing serial framing failures that can turn bytes from another device response into false CPM spikes.

## Why this fork exists

The original reader performs a single `read()` for each expected serial response and does not verify that the requested number of bytes was actually returned. Serial `read()` calls are allowed to return fewer bytes than requested. If that happens, unread bytes can remain in the input stream and the next command can decode them as a different measurement.

That failure mode is especially dangerous for `GETCPM`: two stale bytes can form a mathematically valid but completely false 16-bit CPM value. This fork fixes the acquisition layer instead of hiding high readings with an arbitrary CPM ceiling. A genuinely high, correctly framed CPM value is still published.

## Supported scope

The target is the older GQ family that uses RFC1201-style **two-byte `GETCPM`** responses. GQ's own download/support material associates this protocol/software family with:

- GMC-280
- GMC-300
- GMC-300E
- **GMC-300E Plus / GMC-300E+**
- GMC-320
- GMC-320 Plus / GMC-320+

The primary hardware target for this fork is the GMC-300E Plus family. Compatibility is protocol-based rather than name-based: a device must respond to the RFC1201 `GETVER`, `GETSERIAL`, `GETCPM`, and `GETVOLT` commands with the documented response shapes.

### Not supported

GMC-500/500+/600/600+ use GQ-RFC1801, where `GETCPM` is four bytes and other response formats differ. Those devices are **not** silently treated as RFC1201 devices. GMC-800 and newer/different protocol families are also outside the current scope unless their protocol is explicitly implemented and tested in a future release.

This deliberate boundary keeps the project small enough to remain low-maintenance and avoids unsafe guessing about radiation data formats.

## Main changes

- Exact-length serial reads even when the OS fragments a response across several `read()` calls.
- Stale-input flushing before each request.
- Retry and fail-closed handling for incomplete serial transactions.
- Automatic baud detection across documented legacy rates; a fixed baud can also be configured.
- `GETTEMP` and `GETGYRO` are requested only for GMC-320-family firmware, matching the RFC1201 documentation. On 280/300/300E-family units those fields are published as `null` rather than manufacturing diagnostic values from unsupported commands.
- Version/serial are read once at startup instead of being interleaved with every CPM poll.
- Original non-zero-padded serial identifier is preserved for the MQTT topic so existing Home Assistant MQTT entities can continue to use the same topic.
- Additional `serial_full` and `baud` metadata are published.
- A hard timeout prevents a stuck `mosquitto_pub` process from wedging the service indefinitely.
- No arbitrary high-CPM filter.
- Current Home Assistant architectures: `aarch64` and `amd64`.

## Installation

1. In Home Assistant, open **Settings → Apps → App store** (older UI: **Settings → Add-ons → Add-on Store**).
2. Add this repository:

   `https://github.com/ArrowSK/ha-gmc3xx-fixed`

3. Refresh the store and install **GMC3xx Fixed Radiation Monitor**.
4. Configure the serial device and MQTT connection. Leave `baud` as `auto` unless you know the counter's configured baud.
5. If migrating from another GMC serial reader, **stop the old reader before starting this one**. Two processes must not own the same serial device simultaneously.
6. Start the app and review its log.

See [`gmc3xx_fixed/DOCS.md`](gmc3xx_fixed/DOCS.md) for configuration, compatibility and migration details.

## MQTT compatibility

Topic:

```text
homeassistant/sensor/gmc3xx_<serial>
```

Typical 300/300E-family payload:

```json
{
  "version": "GMC-300Re 4.xx",
  "serial": "compatibility-id",
  "serial_full": "14-digit-hex-id",
  "baud": 115200,
  "cpm": 18,
  "volt": 4.0,
  "temp": null,
  "x": null,
  "y": null,
  "z": null
}
```

On supported GMC-320 firmware, temperature and gyroscope fields are populated and their documented terminator bytes are validated.

## Safety model

This software is a convenience integration, **not a calibrated radiation-safety instrument**. It does not certify dose rate, detector calibration, tube response or regulatory compliance.

The app rejects data because the serial transaction is incomplete or structurally malformed, not because the numerical CPM value looks frightening. Radiation alarms should use suitable persistence/debounce logic and consequential decisions should be confirmed with independent instrumentation.

## Privacy and secrets

No household MQTT username/password, detector serial number, private email address, Home Assistant token, private network address or backup belongs in this repository or in public issue reports. Runtime MQTT credentials are Home Assistant app options and are never logged by the app. Detector identifiers are also redacted from startup logs.

Public test fixtures use synthetic device identifiers only. CI includes a lightweight repository-content privacy check in addition to syntax/build/protocol tests.

## Maintenance expectations

This is a small best-effort compatibility project, not a commercial product or support service. There is no SLA, guaranteed response time, compatibility promise for untested models, or commitment to implement every future GQ protocol. The supported scope is intentionally narrow and protocol-defined so normal Home Assistant updates should require little project-specific maintenance.

Bug reports are useful when they are reproducible and include the exact GQ model/firmware, Home Assistant/app versions, and **redacted** logs. New protocol families should not be added by guessing response lengths.

## Commercial-use licensing reality

This repository is a derivative of GPL-3.0-covered upstream code and therefore remains **GPL-3.0-only**. The GPL permits commercial use, sale and commercial redistribution provided its terms are followed. A "non-commercial use only" restriction cannot lawfully be added to this GPL-covered derivative as an extra restriction.

Accordingly, this project offers **no separate commercial licence, warranty, paid support, endorsement or trademark permission**, but it cannot truthfully promise that GPL-compliant commercial use is forbidden. See [`COMMERCIAL_USE.md`](COMMERCIAL_USE.md) for the rationale.

## Development and tests

CI performs:

- YAML validation and Home Assistant app config assertions;
- ShellCheck;
- C compilation with `-Wall -Wextra -Werror`;
- pseudo-terminal protocol tests that fragment serial replies byte-by-byte;
- separate 300/300E core and GMC-320 diagnostic paths;
- high-CPM pass-through regression testing;
- container build;
- repository-content privacy checks.

## Upstream and provenance

Derived from:

- Original Home Assistant add-on: <https://github.com/gi1mic/gmc320>
- GQ-RFC1201 communication protocol published by GQ Electronics.

The upstream project is GPL-3.0. This derivative remains GPL-3.0-only. See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md).

This project is independent and is not endorsed by GQ Electronics, Home Assistant, or the original repository maintainer.
