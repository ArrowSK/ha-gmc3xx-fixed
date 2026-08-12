# GMC3xx Fixed Radiation Monitor — documentation

## Scope

This app reads GQ GMC counters that use the legacy **GQ-RFC1201** serial protocol and publishes JSON measurements to MQTT.

The supported design target is the RFC1201/two-byte-`GETCPM` family: GMC-280, GMC-300, GMC-300E, GMC-300E Plus, GMC-320 and GMC-320 Plus, subject to firmware support for the core commands used here.

It is not a generic driver for every GQ model. In particular, GMC-500/500+/600/600+ use GQ-RFC1801 and return a four-byte CPM value; they are intentionally rejected rather than guessed at.

## Required protocol features

The app requires documented RFC1201 responses for:

- `GETVER` — 14-byte identity string;
- `GETSERIAL` — 7-byte device serial;
- `GETCPM` — 2-byte big-endian CPM;
- `GETVOLT` — 1-byte battery voltage.

Very old firmware that does not implement `GETSERIAL` is outside the current scope because the serial-derived MQTT topic is part of backward compatibility with the original add-on.

`GETTEMP` and `GETGYRO` are documented by GQ for GMC-320 Re.3.01 or later. The app therefore sends those commands only when the returned hardware/version string begins with `GMC-320`. For 280/300/300E-family units the `temp`, `x`, `y`, and `z` payload fields remain present but are `null`.

## Configuration

### `port`

Serial device presented by Home Assistant OS, normally `/dev/ttyUSB0`.

### `baud`

Default: `auto`.

`auto` tries the legacy RFC1201 rates supported by the build, prioritising the common/default values: 115200, 57600, 19200, 38400, 9600, 4800, 2400 and 1200 baud (plus 14400/28800 when the platform exposes those termios constants).

You can force a numeric baud by entering it as text, for example `19200`. A forced unsupported rate fails closed rather than silently selecting another rate.

GQ's RFC1201 documentation states 57600 for older GMC-300 V3.xx firmware, 115200 for GMC-300 Plus V4.xx and later, and variable baud for GMC-320. Auto detection exists so a migrated installation does not need to know which rate was previously configured.

### `mqtt_server`

MQTT broker hostname or address. `localhost` is supported because the app uses host networking for compatibility with the original add-on.

### `mqtt_port`

MQTT TCP port. Default: `1883`.

### `mqtt_user` / `mqtt_password`

Broker credentials. They are Home Assistant app options, not repository content. The service does not log either value.

### `repeat`

Polling interval in seconds, 2–3600. Default: 60.

## MQTT output

Topic:

```text
homeassistant/sensor/gmc3xx_<serial>
```

Example for a 300/300E-family unit:

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

On a supported GMC-320 firmware, `temp`, `x`, `y`, and `z` are numeric.

### Serial fields and privacy

The original add-on formatted each of the seven serial bytes with `%x`, not `%02x`. To avoid breaking existing MQTT topics:

- `serial` preserves that historical compatibility format and remains part of the topic;
- `serial_full` is the fixed-width hexadecimal identifier.

Neither detector identifier is printed in normal startup logs. Public issue reports should also redact MQTT topics/device serials unless disclosure is genuinely necessary.

## Why this version avoids diagnostic commands on 300/300E-family units

The original reader requested temperature and gyroscope data from every device. GQ's RFC1201 specification documents those commands only for GMC-320 Re.3.01 or later. Sending unsupported commands increases the opportunity for timeouts, stale bytes and misframing while providing no reliable measurement.

For RFC1201 280/300/300E-family devices this app therefore polls only the documented core fields needed for the Home Assistant radiation path: CPM and voltage. Missing optional diagnostics are represented as `null`, not zero.

## What was fixed

The upstream program used one `read(fd, buf, expected_length)` call and decoded the buffer without checking that all requested bytes arrived. POSIX serial reads can legitimately be short. A fragmented version/serial/diagnostic response can therefore leave bytes that a later two-byte `GETCPM` request interprets as radiation data.

This fork:

1. flushes stale input before every transaction;
2. assembles the complete documented reply across multiple `read()` calls;
3. retries incomplete transactions;
4. rejects a sample if framing still cannot be completed;
5. reads identity once at startup;
6. auto-detects/validates the RFC1201 baud rate;
7. avoids model-inappropriate optional commands;
8. validates the `0xAA` terminators for GMC-320 temperature/gyro replies.

There is deliberately **no CPM ceiling**. Transport integrity, not numerical plausibility, determines whether a reading is accepted.

## Migration from the original/local add-on

1. Install this app but **do not start it yet**.
2. Copy the existing serial port, MQTT host/port/user/password and polling interval.
3. Leave `baud` on `auto` unless you have a reason to force the known rate.
4. Stop the old GMC app.
5. Start **GMC3xx Fixed Radiation Monitor**.
6. Confirm the log reports a detected device family and active baud, then `Start sending data`.
7. In Home Assistant Developer Tools, confirm the existing CPM entity continues updating.
8. If automations/scripts restart the old Supervisor app slug, update those references only after the new app is verified.
9. Keep the old app stopped until the replacement has been observed for a suitable period.

**Do not run both apps simultaneously.** Competing for one serial device can itself corrupt communication.

### Expected change for non-320 units

If the old integration exposed `temp`, `x`, `y`, or `z` from a GMC-300/300E-family unit, those entities may become `unknown` because the new payload deliberately sends `null` for diagnostics not documented for that model. CPM and voltage remain the supported measurement path.

## Existing bad recorder history

This app prevents newly malformed serial samples from being published; it does not rewrite Home Assistant Recorder history. Previously stored false spikes remain until they age out or are deliberately purged/rebuilt.

## Troubleshooting

### `Unable to identify an RFC1201-compatible GMC counter`

Check the USB serial path and try a forced known baud if auto detection cannot identify the device. Also verify that the unit belongs to the RFC1201 family; RFC1801/newer devices are intentionally unsupported.

### `incomplete response ... retrying`

A required response did not arrive completely before timeout. Occasional retries can happen during USB disturbances; persistent retries indicate a port/device/firmware/baud problem.

### `Rejected incomplete/malformed serial sample`

At least one required response could not be validated. Nothing is published for that cycle. Missing data is safer than manufacturing a radiation number from misframed bytes.

### `MQTT publish timed out`

The MQTT client did not finish within 15 seconds. The loop continues after skipping that publication.

## Supported Home Assistant architectures

- `aarch64`
- `amd64`

## Maintenance policy

This is a small best-effort compatibility project with no SLA or guaranteed support response. Compatibility additions should be protocol-backed and regression-tested; the project will not grow into a speculative universal GQ driver merely because model names are similar.

The narrow scope is intentional to reduce maintenance burden and radiation-data risk.

## Upstream and licence

Derived from <https://github.com/gi1mic/gmc320>, licensed GPL-3.0. This derivative remains GPL-3.0-only. Commercial use cannot be prohibited by adding a non-commercial clause to the GPL-covered derivative; see the repository's `COMMERCIAL_USE.md`.

This project is independent and not endorsed by GQ Electronics, Home Assistant or the original maintainer.
