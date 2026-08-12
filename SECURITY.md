# Security and privacy policy

## Secrets and personal data

Never commit or post:

- MQTT passwords, usernames tied to a private installation, or broker credentials;
- Home Assistant access tokens or backups;
- private SSH keys;
- private email addresses;
- household/device serial numbers or serial-derived MQTT topics unless disclosure is strictly necessary and explicitly intended;
- private IP addresses, hostnames, addresses, or other household identifiers.

The app accepts MQTT credentials through Home Assistant app options. The repository contains no runtime credentials, and the startup script does not log the MQTT username, password, detector serial number, or serial-derived topic.

Public protocol tests must use clearly synthetic identifiers only.

## Reporting problems

For ordinary bugs, open a GitHub issue with the app version, Home Assistant version, device model/firmware, and redacted logs. The issue template reminds reporters to remove device serials, MQTT topics, network details and credentials.

For a security-sensitive report, do not publish working credentials or private data. This is a best-effort hobby project with no private support SLA; if disclosure itself would expose a secret, rotate/revoke the secret first and avoid posting it.

## Radiation-data integrity

A false radiation reading can cause unnecessary alarm or, if filtered incorrectly, conceal a genuine event. Changes to serial parsing should therefore preserve these principles:

- reject malformed/incomplete transport data;
- do not reject a value solely because it is high;
- do not silently substitute zero for missing data;
- do not send model-inappropriate protocol commands merely to populate optional fields;
- keep failure diagnostics useful without exposing installation identifiers.
