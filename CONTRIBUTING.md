# Contributing

This is a small best-effort compatibility project. Contributions are welcome, but there is no SLA or guaranteed maintainer response time.

## Compatibility boundary

The current supported design target is the legacy GQ **RFC1201** / two-byte-`GETCPM` family. Do not add a new model merely because its product name starts with `GMC`.

Protocol changes should include:

1. a primary-source protocol reference or captured evidence sufficient to establish response lengths/semantics;
2. fail-closed parsing for incomplete or structurally malformed replies;
3. pseudo-terminal regression tests, including fragmented reads;
4. documentation of what was verified and what remains unverified.

RFC1801/four-byte-CPM devices must not be routed through the RFC1201 decoder.

## Radiation-data rules

- Never add an arbitrary maximum CPM filter as a substitute for transport validation.
- Never silently convert missing/failed readings to zero.
- Avoid issuing commands not documented for the identified model family merely to populate optional fields.
- Treat response length, endianness and documented terminators as part of the data contract.

## Privacy

Do not commit or paste real installation identifiers into tests, examples or issues. Use synthetic values for:

- detector serials and serial-derived MQTT topics;
- MQTT usernames/passwords;
- private hostnames/IP addresses;
- email addresses, tokens and Home Assistant IDs tied to a real household.

The repository is public. Assume every commit and issue is permanently discoverable.

## Tests

Before proposing changes, run the same checks as CI where practical: YAML parse/config assertions, ShellCheck, C compilation with warnings as errors, protocol regression tests and container build.

## Licence

This repository is derived from GPL-3.0 upstream code and remains GPL-3.0-only. Do not add incompatible restrictions, including a non-commercial-use clause. See `COMMERCIAL_USE.md`.
