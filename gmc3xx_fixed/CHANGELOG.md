# Changelog

## 1.2.0 — 2026-08-12

- Renamed the visible app to **GMC3xx Radiation Monitor**. The internal slug stays `gmc3xx_fixed` so existing installations update normally.
- The serial port now stays open while readings are flowing. It is no longer reopened and reinitialised for every polling cycle.
- Added automatic reconnect after a persistent serial failure or USB disconnect.
- Added `port: auto` for new installations. The app scans common USB serial paths, uses one compatible GMC counter when there is exactly one, and refuses to guess if several compatible counters are attached.
- New installations can use Home Assistant's MQTT service without copying a broker username/password into the app. Manual MQTT settings remain available and existing manual settings are kept on upgrade.
- Automatic MQTT mode refreshes Home Assistant service credentials after a failed publish and retries once immediately.
- MQTT failure warnings are rate-limited while the app continues retrying in the background.
- Added a Supervisor watchdog health port.
- Changed the default polling interval for new installations to 5 seconds.
- Added a new app icon and rewrote the setup/migration documentation in plain language.
- Added a persistent-stream regression test. Multiple readings must use one serial open/heartbeat cycle rather than reopening the device each time.
- Confirmed the 1.1.2 serial timing path on real GMC-300E Plus hardware reporting `GMC-300Re 4.62` at 19200 baud. Live CPM and the existing Home Assistant dose-rate entity both updated normally.
- Kept the existing MQTT state-topic format and the rule that correctly framed high CPM values are never hidden by an arbitrary numerical filter.

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
