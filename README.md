# GMC3xx Radiation Monitor for Home Assistant

This repository now provides two independent ways to use supported GQ GMC Geiger counters with Home Assistant:

- the existing **Home Assistant App**, which reads USB and publishes measurements to MQTT;
- a **native HACS integration**, which reads the USB device directly from Home Assistant Core and creates native sensor entities.

The existing App remains supported and its runtime files are unchanged. **Do not run the App and HACS integration against the same counter at the same time.** Installing the HACS files alone does not open the serial port; the native integration only probes the device when you explicitly add it under Devices & services.

It is aimed at the older GQ models that use the RFC1201 protocol, including the GMC-300E Plus and GMC-320 family. The code is intentionally conservative with serial data: if a reply is incomplete, that reading is dropped instead of being turned into a CPM number.

## Why this project exists

The older `gi1mic/gmc320` reader assumed that one serial `read()` call would always return a complete reply. USB serial does not guarantee that. A reply can arrive in pieces, and bytes left behind from one command can then be mistaken for the next value.

For a Geiger counter that matters. Two stray bytes can look like a perfectly valid but completely false CPM reading.

Both installation paths preserve the same protocol safeguards:

- they wait for the complete documented reply;
- they clear stale input before a command;
- they retry an incomplete transaction a limited number of times;
- they never reject a reading just because the CPM number is high;
- they keep the serial port open while readings are flowing instead of reopening it every cycle;
- they reconnect automatically if the USB link disappears or the counter stops answering.

## Home Assistant App

### What is automatic in 1.2.0

A new App installation can normally be left at the defaults.

- **Serial device:** `auto` looks for one compatible GMC counter on common USB serial paths. If more than one compatible counter is found, the app asks you to choose one instead of guessing.
- **Baud rate:** `auto` tries the supported RFC1201 rates and uses the one that answers correctly.
- **MQTT:** when the MQTT server field is blank, the app asks Home Assistant for the MQTT service connection details. No broker username or password needs to be copied into the app.
- **MQTT recovery:** if Home Assistant rotates the temporary MQTT credentials, the app asks for fresh service details and retries.
- **USB recovery:** if the serial stream fails, the app closes it, waits briefly, finds the counter again and reconnects.
- **Supervisor watchdog:** Home Assistant can see that the app is alive and restart it if the app itself stops responding.

Manual serial and MQTT settings are still available for unusual setups.

### Install the App

1. Connect the GMC counter to the Home Assistant machine by USB.
2. In Home Assistant, open **Settings → Apps → App store**.
3. Add this repository:

   `https://github.com/ArrowSK/ha-gmc3xx-fixed`

4. Install **GMC3xx Radiation Monitor**.
5. If this is a new setup, leave `port`, `baud` and MQTT at their defaults and start the app.

If you are replacing another GMC reader, stop the old one **before** starting this app. Two programs must not talk to the same serial device at the same time.

See [SETUP.md](SETUP.md) for the full App first-install and migration guide. The Home Assistant Documentation tab uses the same practical instructions from [`gmc3xx_fixed/DOCS.md`](gmc3xx_fixed/DOCS.md).

## HACS native integration

The native integration is an alternative to the App, not an additional reader to run beside it. MQTT is not required.

1. Add `https://github.com/ArrowSK/ha-gmc3xx-fixed` to HACS as a custom repository of type **Integration**.
2. Install **GMC3xx Radiation Monitor** in HACS and restart Home Assistant when requested.
3. **Stop the GMC3xx Radiation Monitor App before adding the integration.**
4. Open **Settings → Devices & services → Add integration → GMC3xx Radiation Monitor**.
5. Leave serial port and baud on `auto` unless you have more than one compatible counter.
6. Confirm in the setup form that the App has been stopped, then continue.

The native integration creates `GMC3xx CPM` and `GMC3xx Voltage` sensors. GMC-320-family firmware also gets temperature and gyroscope X/Y/Z sensors. It reconnects to the same physical serial number if Linux assigns a different USB device path after reconnect.

See [HACS.md](HACS.md) for migration, safety and troubleshooting details.

## Supported devices

The supported path is the RFC1201 family with a **two-byte `GETCPM` reply** and the documented `GETVER`, `GETSERIAL` and `GETVOLT` commands. The intended models are:

- GMC-280
- GMC-300
- GMC-300E
- GMC-300E Plus / GMC-300E+
- GMC-320
- GMC-320 Plus / GMC-320+

The project has been tested on real GMC-300E Plus hardware whose firmware identifies itself as `GMC-300Re 4.62`.

GMC-500/500+/600/600+ use RFC1801 with different reply formats, including a four-byte CPM value. They are not handled by this release. GMC-800 and other newer protocol families are also outside the current scope.

## Existing Home Assistant MQTT entities

The App state topic remains:

```text
homeassistant/sensor/gmc3xx_<serial>
```

A typical GMC-300/300E-family payload looks like this:

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

The historical non-zero-padded `serial` formatting is kept on purpose because older Home Assistant MQTT configurations may already use that exact topic. `serial_full` is included as cleaner metadata but does not replace the compatibility topic.

For 280/300/300E-family devices, temperature and gyroscope fields are `null`. GQ documents those commands for the GMC-320 path, so neither implementation requests them from models that are not meant to answer them.

## About dose rate

Neither implementation applies a universal CPM-to-µSv/h conversion because that factor depends on the detector/tube and calibration. If your Home Assistant setup already has a dose-rate template with the factor you use for your counter, it can continue using the CPM entity after migration.

## Safety

This is a Home Assistant integration, not a calibrated radiation-safety instrument. It cannot verify tube calibration or replace appropriate measurement equipment.

The serial checks are deliberately about **whether the reply is complete**, not whether the number looks normal. A correctly framed high CPM value is allowed through. There is no hidden spike ceiling.

## Privacy

Normal App logs do not print the detector serial number, the serial-derived MQTT topic, the MQTT username or the MQTT password. HACS diagnostics omit the detector serial number and Linux device path. Public issue reports should keep those details redacted as well.

The repository CI also checks text files for common accidental private-data patterns.

## Development

The existing App CI continues to check:

- YAML and app configuration errors;
- shell syntax and ShellCheck issues;
- C compiler warnings (`-Wall -Wextra -Werror`);
- fragmented serial replies delivered one byte at a time;
- delayed stale bytes after heartbeat shutdown;
- a persistent multi-reading serial stream that must not reopen the port each cycle;
- high CPM pass-through;
- container build;
- presence and basic validity of the app icon;
- common private-data leaks in repository text.

The HACS path has a separate workflow for Python syntax, serial protocol regression tests, HACS repository validation and hassfest. Keeping the workflows separate means adding the HACS integration does not replace or weaken the existing App checks.

## Licence and upstream

This code is derived from [`gi1mic/gmc320`](https://github.com/gi1mic/gmc320) and remains **GPL-3.0-only**. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

GPL-3.0 permits commercial use and redistribution under its terms. This project does not offer a separate commercial licence, paid support or warranty. See [COMMERCIAL_USE.md](COMMERCIAL_USE.md) for the licensing note.

This project is independent and is not endorsed by GQ Electronics, Home Assistant or the original repository maintainer.
