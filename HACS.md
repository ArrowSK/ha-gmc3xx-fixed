# HACS native integration

The repository contains two independent installation paths for the same supported GMC hardware.

## Important: choose one runtime path

The existing **Home Assistant App** remains supported and unchanged. It owns the USB serial device and publishes measurements to MQTT.

The **HACS integration** talks to the same USB device directly from Home Assistant Core and creates native Home Assistant sensor entities. MQTT is not required.

Do not run both readers at the same time. Two processes sending RFC1201 commands to one serial port can interleave replies and produce invalid data. Installing the HACS files does not open the serial port; the integration only probes the device after you explicitly add it in **Settings → Devices & services** and confirm that the App has been stopped.

## HACS installation

1. Keep the existing App running while HACS downloads the repository if you want. Installation alone does not touch USB.
2. In HACS, add `https://github.com/ArrowSK/ha-gmc3xx-fixed` as a custom repository of type **Integration**.
3. Install **GMC3xx Radiation Monitor**.
4. Restart Home Assistant when HACS asks.
5. **Stop the GMC3xx Radiation Monitor App.**
6. Open **Settings → Devices & services → Add integration → GMC3xx Radiation Monitor**.
7. Leave serial port and baud rate on `auto` unless you have more than one compatible counter.
8. Confirm that the App is stopped, then submit.

If you return to the App later, first remove or disable the HACS config entry so Home Assistant releases the serial port, then start the App.

## Native entities

For all supported devices:

- `GMC3xx CPM`
- `GMC3xx Voltage`

For GMC-320-family firmware, the integration also exposes temperature and gyroscope X/Y/Z.

The integration deliberately does not invent a universal CPM-to-µSv/h conversion. Detector response depends on tube and calibration. An existing Home Assistant template that calculates dose rate from `sensor.gmc3xx_cpm` can continue to do so after migration if its calibration factor is appropriate for the physical counter.

## Protocol and recovery behavior

The HACS implementation mirrors the working App reader rather than using a simplified serial parser. It waits for complete replies, clears stale input, retries incomplete transactions, keeps one serial connection open, permits correctly framed high CPM readings, validates identity and GMC-320 terminators, reconnects after serial failure, and searches for the same physical serial number if Linux assigns a different device path.

## Supported hardware

This first HACS release intentionally matches the App's RFC1201 scope: GMC-280, GMC-300, GMC-300E, GMC-300E Plus, GMC-320 and GMC-320 Plus families using the two-byte `GETCPM` reply.

GMC-500/500+/600/600+ and GMC-800 families use different protocol/reply formats and are not supported by this release.

## Privacy and diagnostics

Home Assistant diagnostics omit the counter serial number and Linux device path. They include firmware family, baud rate, polling interval, reconnect count and update status.
