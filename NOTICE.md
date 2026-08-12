# Provenance and modification notice

## Upstream

This repository is a modified derivative of:

- **Project:** `gi1mic/gmc320`
- **Repository:** https://github.com/gi1mic/gmc320
- **License:** GNU General Public License v3.0

The upstream `rootfs/gmc320.c` header states that the sensor code was based in part on code from Christoph Haas. That provenance is preserved in the modified source.

## Modifications in this repository

Modified in 2026 for a public Home Assistant compatibility fork.

Material changes include:

1. Replaced single-shot serial reads with exact-length reads that tolerate POSIX short reads and fragmented USB/serial delivery.
2. Added input flushing and transaction retries so stale response bytes do not cross command boundaries.
3. Separated identity acquisition from recurring measurement polling.
4. Added RFC1201 legacy baud auto-detection and fixed-baud validation.
5. Broadened the documented target to the RFC1201 GMC-280/300/300E/300E Plus/320 family while deliberately excluding incompatible RFC1801/four-byte-CPM protocols.
6. Stopped sending GMC-320-only `GETTEMP`/`GETGYRO` commands to 280/300/300E-family units; unsupported diagnostics are represented as `null`.
7. Added validation of documented temperature/gyroscope terminator bytes on the GMC-320 path.
8. Preserved upstream serial-number formatting in the `serial` field for MQTT topic compatibility and added `serial_full` as canonical zero-padded metadata.
9. Added MQTT timeout handling and safer shell quoting.
10. Added privacy-conscious logging, public documentation, CI, and pseudo-terminal protocol regression tests.

No arbitrary CPM maximum filter is applied. Correctly framed high readings are passed through unchanged.

## Licence boundary

Because this is a GPL-3.0 derivative, commercial use cannot be prohibited by adding a non-commercial restriction. The repository therefore remains GPL-3.0-only and does not pretend otherwise. See `COMMERCIAL_USE.md`.

This project is independent and is not endorsed by GQ Electronics, Home Assistant, or the upstream maintainer.
