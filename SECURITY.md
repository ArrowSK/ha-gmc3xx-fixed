# Security and privacy

## Supported release

Security and reliability fixes are applied to the current release line of **GMC3xx Radiation Monitor**. This is a best-effort community project; there is no security SLA.

## Reporting a security issue

Do **not** open a public issue containing secrets or personal information. If GitHub private vulnerability reporting is available for the repository, prefer that mechanism for a genuine security vulnerability. Otherwise, first remove all sensitive material and report only the minimum reproducible technical details publicly.

Never include:

- MQTT usernames or passwords;
- Home Assistant tokens or backup contents;
- detector serial numbers or serial-derived MQTT topics;
- private email addresses;
- private IP addresses or internal hostnames;
- household/location details;
- screenshots that expose unrelated Home Assistant data.

## Reliability issues are also safety-relevant

A serial framing bug can create a false radiation measurement even when it is not a conventional cybersecurity vulnerability. Please report reproducible cases where bytes can cross command boundaries, partial responses can be accepted, or the app can publish malformed measurements.

The intended safety properties are:

- exact documented response lengths;
- bounded serial timeouts and retries;
- stale-input draining;
- fail-closed behaviour after persistent acquisition failure;
- no arbitrary high-CPM suppression;
- GMC-320-only commands sent only to the appropriate identified model path;
- automatic session recreation after transport failure.

## Credentials

When `mqtt_server` is blank, the app can use the MQTT service details supplied to Home Assistant apps at runtime. When a manual/external broker is configured, credentials remain app options. Neither path should print credentials to normal logs.

## Dependency and base-image updates

The app builds on the Home Assistant base image and Alpine packages installed during the image build. CI rebuilds the complete app image so obvious dependency/build regressions are detected before a release is considered healthy.

## Safety disclaimer

This project improves software transport integrity but does not turn a consumer Geiger counter into certified radiation-safety equipment. Calibration, detector physics and consequential safety decisions remain outside the scope of this software.
