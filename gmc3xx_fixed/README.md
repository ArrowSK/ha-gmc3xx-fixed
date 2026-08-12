# GMC3xx Fixed Radiation Monitor

Robust USB-serial to MQTT bridge for the legacy GQ **RFC1201** Geiger-counter family, including GMC-280/300/300E/300E Plus/320/320 Plus where the required protocol commands are supported.

This app is a compatibility fork of [`gi1mic/gmc320`](https://github.com/gi1mic/gmc320). It fixes serial short-read/framing failures without applying an arbitrary upper limit to CPM values.

Highlights:

- exact-length serial reads with retry and stale-input flushing;
- automatic legacy baud detection, with optional forced baud;
- 300/300E-safe core polling without unsupported 320-only diagnostic commands;
- validated GMC-320 temperature/gyroscope replies;
- MQTT publish timeout protection;
- same legacy serial-derived MQTT topic for existing Home Assistant setups;
- no detector identifiers or MQTT credentials written to normal logs.

GMC-500/600-family RFC1801 devices and other four-byte-CPM protocols are intentionally not supported by this release.

Read the **Documentation** tab before migrating. The old GMC reader must be stopped before this app starts because both cannot own the same serial device.
