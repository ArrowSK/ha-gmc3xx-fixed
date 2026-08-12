# GMC3xx Radiation Monitor — setup and reference

## The short version

For a new installation with one supported GQ GMC counter:

1. Plug the counter into USB.
2. Install the app.
3. Leave **Serial device** on `auto`.
4. Leave **Serial baud rate** on `auto`.
5. Leave **MQTT server override** blank so Home Assistant supplies the MQTT connection.
6. Leave the polling interval at 5 seconds unless you have a reason to change it.
7. Start the app.

If you are replacing another GMC reader, stop the old one first. Two processes talking to one serial device can interfere with each other.

## What you should see in the log

A normal connection looks like:

```text
Starting GMC3xx Radiation Monitor
MQTT: using Home Assistant's MQTT service
Serial device: USB serial device (...)
Detected device family: GMC-...
Active serial baud: ...
Connected. Measurements are now being sent to MQTT.
```

The detector serial number, serial-derived MQTT topic, MQTT username and MQTT password are not printed in normal logs.

## Supported devices

This app is for GQ counters using the older RFC1201 protocol with a two-byte `GETCPM` reply. The intended family is:

- GMC-280
- GMC-300
- GMC-300E
- GMC-300E Plus / GMC-300E+
- GMC-320
- GMC-320 Plus / GMC-320+

It has been tested on real GMC-300E Plus hardware reporting firmware identity `GMC-300Re 4.62`.

The app expects these core RFC1201 commands and reply sizes:

- `GETVER` — 14 bytes
- `GETSERIAL` — 7 bytes
- `GETCPM` — 2 bytes, big-endian
- `GETVOLT` — 1 byte

GMC-500/500+/600/600+ use RFC1801 and different reply formats, including four-byte CPM. They are not supported here. GMC-800 and other newer protocol families are also outside this release.

## Configuration

### Serial device

Default: `auto`.

Automatic mode checks common `/dev/serial/by-id/`, `/dev/ttyUSB*` and `/dev/ttyACM*` paths. Paths that resolve to the same physical device are tested only once.

If one compatible GMC counter answers, it is selected. If more than one answers, the app asks you to choose a device explicitly instead of guessing.

You can enter a fixed serial path at any time. When available, a `/dev/serial/by-id/...` path is generally a better long-term choice than `/dev/ttyUSB0` because it is less likely to change after reconnects.

### Serial baud rate

Default: `auto`.

Automatic mode tries the supported RFC1201 rates. You can enter a numeric rate, for example `19200`, when you already know the setting.

Once the counter is identified, the app keeps that serial connection open while it is sampling. It does not reopen the port for every reading.

### MQTT server override

Default: blank.

When this field is blank, the app uses Home Assistant's MQTT service API to obtain the broker host, port and temporary credentials. If those credentials change, a failed publish triggers a refresh and one immediate retry.

To use a separate broker, enter its hostname/address here. The MQTT port, username and password options then become the manual connection settings.

Existing installations that already contain a manual MQTT server keep using it after updating; 1.2.0 does not silently change a working broker configuration.

### MQTT port / username / password

Used only when **MQTT server override** is set.

The password is stored as a Home Assistant app option and is never printed by the app.

### Polling interval

Default: 5 seconds. Allowed range: 2–3600 seconds.

## MQTT payload

The compatibility topic remains:

```text
homeassistant/sensor/gmc3xx_<serial>
```

Typical GMC-300/300E-family payload:

```json
{
  "version": "GMC-300Re 4.xx",
  "serial": "compatibility-id",
  "serial_full": "14-digit-hex-id",
  "baud": 19200,
  "cpm": 18,
  "volt": 4.0,
  "temp": null,
  "x": null,
  "y": null,
  "z": null
}
```

The `serial` field intentionally keeps the original add-on's non-zero-padded formatting because existing Home Assistant MQTT topics may already depend on it. `serial_full` is a fixed-width form included as metadata.

For GMC-280/300/300E-family units, `temp`, `x`, `y` and `z` are `null`. GQ documents temperature/gyroscope commands for the GMC-320 path, so the app does not send those commands to models that are not meant to answer them.

## Why incomplete replies are rejected

The older reader called `read()` once and decoded whatever was in the buffer. A serial read is allowed to return fewer bytes than requested. If one response arrived in pieces, leftover bytes could cross into the next command and a pair of unrelated bytes could be interpreted as CPM.

This reader instead:

1. clears stale input before each command;
2. waits until the exact documented reply length has been assembled;
3. retries a short/incomplete transaction;
4. rejects the sample if the reply still cannot be completed;
5. reconnects the serial stream after a persistent sampling failure.

The 500 ms quiet period after `HEARTBEAT0` is kept because real GMC-300E Plus hardware showed that starting the first command too quickly could lead to an incomplete first reply.

There is **no numerical CPM ceiling**. A complete, correctly framed high CPM reading is published as-is.

## Automatic recovery

### USB/counter problem

A persistent serial failure ends the current stream. The app waits five seconds, finds the configured/automatic device again, identifies it and resumes.

### MQTT problem

A failed publication does not stop the serial reader. The app keeps trying. In automatic MQTT mode it refreshes Home Assistant's service credentials after a failure. Log warnings are rate-limited to avoid one warning every polling cycle.

### App problem

The app exposes a small local health port for the Home Assistant Supervisor watchdog. If the app process stops responding, Supervisor can restart it.

## Migration from the original/local add-on

1. Install GMC3xx Radiation Monitor but do not start it yet.
2. Disable any Home Assistant automation that can restart the old GMC add-on.
3. Stop the old GMC add-on.
4. Start this app.
5. Confirm the device family and baud in the log.
6. Confirm your existing Home Assistant CPM entity keeps changing.
7. Only then update any recovery automation to point to this app's Supervisor slug.
8. Keep the old app stopped until you are satisfied with the new one.

Do not run both readers together.

### Updating from 1.1.x

The internal slug remains `gmc3xx_fixed` so Home Assistant treats 1.2.0 as an update to the same installed app.

Your existing options stay in place. If you already use a stable `/dev/serial/by-id/...` path, keep it. If you already use manual MQTT settings, they remain active. You can opt into the new automatic MQTT connection later by clearing **MQTT server override**.

## Home Assistant entities

The app publishes MQTT data; it does not replace your Home Assistant entity configuration during an upgrade. Existing MQTT sensors can continue reading the same topic and JSON keys.

For a new setup, see the repository's `SETUP.md` for a small MQTT YAML example.

## Dose-rate conversion

CPM-to-µSv/h conversion depends on the counter/tube and calibration. The app therefore publishes CPM and leaves any dose conversion to Home Assistant or another calibrated layer you control.

## Existing Recorder history

Updating the app prevents new incomplete serial frames from being published. It does not rewrite old Home Assistant Recorder history. Previously stored false spikes remain until Recorder ages them out or you deliberately clean them up.

## Privacy when reporting a problem

Before posting a public log or issue, remove:

- detector serial numbers;
- the serial-derived MQTT topic;
- MQTT credentials;
- private email addresses;
- private hostnames/IP addresses;
- Home Assistant tokens;
- location or household details that are not needed to reproduce the problem.

Normal startup logs already hide the detector identifier and MQTT credentials.

## Licence

Derived from `gi1mic/gmc320`, GPL-3.0. This project remains GPL-3.0-only.

This project is independent and is not endorsed by GQ Electronics, Home Assistant or the original maintainer.
