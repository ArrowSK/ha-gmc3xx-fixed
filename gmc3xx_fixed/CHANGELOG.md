# Changelog

## 1.1.2 — 2026-08-12

- Restored the effective 500 ms post-`HEARTBEAT0` quiet period used by the upstream reader before the first polling command.
- This targets GMC-300-series firmware that can otherwise ignore the first `GETCPM` immediately after opening the port and disabling heartbeat.
- Added a pseudo-terminal regression condition with deliberately delayed stale bytes after `HEARTBEAT0`; those bytes must be discarded and must never become a false CPM value.
- No numerical CPM ceiling or spike filter was added.

## 1.1.1 — 2026-08-12

- Fixed Home Assistant startup on current Supervisor/s6-overlay by declaring `init: false`, as required for apps that use the Home Assistant base image with a direct `CMD` script.
- Added a CI assertion so future releases cannot accidentally omit the required `init: false` setting.

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
