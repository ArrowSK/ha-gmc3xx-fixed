# Provenance and modification notice

## Upstream

This repository is a modified derivative of:

- **Project:** `gi1mic/gmc320`
- **Repository:** https://github.com/gi1mic/gmc320
- **License:** GNU General Public License v3.0

The upstream `rootfs/gmc320.c` header states that the sensor code was based in part on code from Christoph Haas. That provenance is kept in the modified source.

## Main changes in this repository

The Home Assistant app and serial reader were changed in 2026 to make the RFC1201 path safer and easier to run unattended.

The main changes are:

1. exact-length serial reads that tolerate short/fragmented USB serial delivery;
2. stale-input flushing and bounded retries between protocol commands;
3. model-aware handling of optional GMC-320 temperature/gyroscope commands;
4. validation of documented reply lengths and GMC-320 terminator bytes;
5. automatic RFC1201 baud detection with an optional fixed-baud setting;
6. the 500 ms quiet period after `HEARTBEAT0`, retained after testing on real GMC-300E Plus hardware;
7. a persistent serial stream so the USB device is not reopened for every reading;
8. automatic reconnect after serial/USB failure;
9. optional automatic serial-device discovery when exactly one compatible counter is present;
10. automatic use of Home Assistant's MQTT service for new installations, with manual broker settings still available;
11. MQTT credential refresh/retry in automatic mode and a publish timeout;
12. preservation of the original serial-number formatting in the compatibility MQTT topic, plus a fixed-width `serial_full` metadata field;
13. privacy-conscious logging and public issue guidance;
14. pseudo-terminal regression tests, including fragmented reads, delayed stale bytes, persistent multi-sample streaming and high-CPM pass-through;
15. Home Assistant app packaging, documentation, CI and app-store icon.

No arbitrary CPM maximum filter is applied. A complete, correctly framed high reading is passed through unchanged.

## Licence boundary

Because this is a GPL-3.0 derivative, commercial use cannot be prohibited by adding a non-commercial restriction. The repository remains GPL-3.0-only. See `COMMERCIAL_USE.md`.

This project is independent and is not endorsed by GQ Electronics, Home Assistant or the upstream maintainer.
