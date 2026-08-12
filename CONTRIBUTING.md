# Contributing

Contributions to **GMC3xx Radiation Monitor** are welcome when they keep the project small, testable and safe for unattended Home Assistant use.

## Scope first

The supported protocol scope is the legacy GQ-RFC1201/two-byte-`GETCPM` family documented in the project README. Do not add a new GMC family by guessing packet sizes or by applying a numerical filter to suspicious readings.

For protocol changes, provide at least one of:

- public manufacturer protocol documentation;
- a reproducible, privacy-redacted command/response trace;
- a deterministic synthetic fixture that reproduces the behaviour.

RFC1801/four-byte-CPM devices and newer unrelated protocol families should be implemented as explicit protocol paths rather than silently treated as RFC1201.

## Reliability requirements

Changes to the acquisition path should preserve these invariants:

- incomplete serial reads are never decoded as measurements;
- stale input is cleared at command boundaries;
- retries and timeouts are bounded;
- persistent serial failure fails closed and causes reconnect/re-identification;
- normal polling keeps a persistent serial session rather than reopening USB every cycle;
- 280/300/300E-family devices are not sent GMC-320-only diagnostic commands;
- correctly framed high CPM values are allowed through unchanged;
- the legacy MQTT topic identifier remains compatible unless a migration is explicitly designed and documented.

## Tests

Before submitting a change, run or reproduce the CI checks:

- YAML/app metadata validation;
- ShellCheck and `bash -n`;
- C compilation with `-Wall -Wextra -Werror`;
- pseudo-terminal protocol regression tests;
- persistent-session tests;
- privacy-content scanning;
- Home Assistant app container build.

A protocol bug fix should normally include a regression test that fails before the fix and passes after it.

## Privacy

Never put real detector serials, serial-derived MQTT topics, MQTT credentials, Home Assistant tokens, private email addresses, private IP addresses, private hostnames, household/location details or backups in a commit, test fixture, issue or pull request.

Use synthetic identifiers in tests. Redact logs before posting them publicly.

## Bug reports

A useful bug report includes the exact GMC model, firmware string, app version, Home Assistant version, configured baud mode and a short **redacted** log showing the failure. Do not include credentials or detector identifiers.

## Maintenance expectations

This is a best-effort compatibility project without an SLA. New functionality should reduce or preserve maintenance burden, not create an obligation to support undocumented protocol families indefinitely.

## Licence

By contributing, you agree that your contribution is distributed under the repository's **GPL-3.0-only** licence and is compatible with the upstream derivative-work obligations.
