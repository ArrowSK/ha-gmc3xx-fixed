# Changelog

## 1.1.0 — 2026-08-12

- Expanded the intended compatibility scope to the GQ RFC1201/two-byte-CPM family: GMC-280, GMC-300, GMC-300E, GMC-300E Plus, GMC-320 and GMC-320 Plus, subject to firmware command support.
- Added automatic detection of documented legacy baud rates and a fixed-baud override.
- Stopped issuing GMC-320-only `GETTEMP`/`GETGYRO` commands to 280/300/300E-family units. Their optional diagnostic fields now remain present as `null`.
- Added validation of the documented `0xAA` temperature terminator as well as the gyroscope terminator on the GMC-320 path.
- Added `baud` to MQTT payload metadata.
- Redacted detector serial identifiers from normal startup logs.
- Added explicit RFC1801/four-byte-CPM exclusion rather than guessing incompatible packet formats.
- Expanded protocol tests to cover core-only and GMC-320 diagnostic paths at multiple baud settings.
- Added privacy scanning/documentation and clarified best-effort maintenance expectations.
- Documented the GPL-3.0 commercial-use constraint: a non-commercial restriction cannot be added to this GPL-derived code.

## 1.0.0 — 2026-08-12

- Initial public compatibility fork of `gi1mic/gmc320`.
- Added exact-length serial reads that tolerate fragmented POSIX reads.
- Added stale-input flushing and retry/fail-closed handling around serial transactions.
- Separated identity reads from recurring sample polling.
- Preserved legacy MQTT topic/serial formatting and added canonical `serial_full` metadata.
- Added MQTT publish timeout handling.
- Added pseudo-terminal regression tests and CI validation.
- Kept correctly framed high CPM values unfiltered.
