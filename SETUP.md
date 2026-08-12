# Setup guide

This is the practical setup guide for **GMC3xx Radiation Monitor**.

## New installation

For a normal Home Assistant OS / Supervised installation with one supported GQ GMC counter and the Home Assistant MQTT service already available:

1. Plug the counter into USB.
2. Add `https://github.com/ArrowSK/ha-gmc3xx-fixed` to the Home Assistant App store repositories.
3. Install **GMC3xx Radiation Monitor**.
4. Leave these settings at their defaults:
   - Serial device: `auto`
   - Serial baud rate: `auto`
   - MQTT server override: blank
   - Polling interval: `5`
5. Start the app.

A normal startup looks roughly like this:

```text
Starting GMC3xx Radiation Monitor
MQTT: using Home Assistant's MQTT service
Serial device: USB serial device (...)
Detected device family: GMC-...
Active serial baud: ...
Connected. Measurements are now being sent to MQTT.
```

The app hides the detector identifier and MQTT credentials from normal logs.

## Migrating from another GMC add-on

Do not let two readers use the same USB serial device at once.

1. Install GMC3xx Radiation Monitor, but do not start it yet.
2. Note the old reader's polling interval and any MQTT settings you intentionally use.
3. Stop any automation that can automatically restart the old reader.
4. Stop the old reader.
5. Start GMC3xx Radiation Monitor.
6. Check the log for a successful device detection and MQTT connection.
7. Check the existing Home Assistant CPM entity. If it keeps changing, the MQTT compatibility topic is working.
8. Only after that should you change any Home Assistant recovery automation so it points to the new app slug.
9. Keep the old reader installed but stopped until you are comfortable with the new one.

The internal app slug remains `gmc3xx_fixed` so upgrades from the earlier releases continue to work. The visible app name no longer uses that wording.

## Updating from 1.1.x

Existing app options are kept by Home Assistant during an update.

If you already entered a manual MQTT server such as `localhost`, 1.2.0 will continue using it. Nothing is silently switched underneath a working installation.

If you want to use Home Assistant's automatic MQTT service instead, clear the **MQTT server override** field and save the app configuration. The username/password fields are then ignored because Home Assistant supplies temporary service credentials directly to the app.

A manually selected `/dev/serial/by-id/...` path is also kept. That is a good choice and does not need to be changed to `auto` unless you want automatic serial discovery.

## Home Assistant MQTT sensors

This app publishes one JSON message containing the readings. Existing MQTT YAML can keep using the same state topic.

For a new Home Assistant setup, create MQTT sensors that read the JSON keys you need. Replace `<serial>` with the compatibility identifier used in the topic for your counter.

Example:

```yaml
mqtt:
  sensor:
    - name: "GMC3xx CPM"
      state_topic: "homeassistant/sensor/gmc3xx_<serial>"
      unique_id: gmc3xx_cpm
      unit_of_measurement: "CPM"
      state_class: measurement
      expire_after: 300
      value_template: "{{ value_json.cpm }}"

    - name: "GMC3xx voltage"
      state_topic: "homeassistant/sensor/gmc3xx_<serial>"
      unique_id: gmc3xx_voltage
      unit_of_measurement: "V"
      device_class: voltage
      state_class: measurement
      expire_after: 300
      value_template: "{{ value_json.volt }}"
```

The serial/topic is intentionally not printed in the normal app log. If you are doing a brand-new setup and need to determine it, use an MQTT client or Home Assistant's MQTT debug/listen tools locally. Do not paste a real detector serial into a public issue.

## Dose-rate sensor

There is no universal CPM-to-µSv/h factor that is correct for every GMC model/tube. Keep the CPM reading as the source value and apply the conversion factor appropriate to your counter/calibration in Home Assistant if you need a dose-rate entity.

## Configuration reference

### Serial device

`auto` searches, in order, common stable `/dev/serial/by-id/` links and common `/dev/ttyUSB*` / `/dev/ttyACM*` devices. Duplicate paths pointing to the same physical device are ignored.

If exactly one compatible RFC1201 GMC counter answers, it is used. If more than one answers, the app stops guessing and asks you to configure a specific path.

You can always enter a fixed path yourself. A `/dev/serial/by-id/...` path is preferable to `/dev/ttyUSB0` when it is available because it usually survives USB device-number changes.

### Baud rate

`auto` tries the legacy RFC1201 rates supported by the platform. A numeric rate such as `19200`, `57600` or `115200` can be used when you know the counter's setting.

Once a stream is connected, the port stays open between readings. The app does not reopen the serial device every polling cycle.

### MQTT server override

Leave blank for Home Assistant's MQTT service. This is the recommended setting for a new installation.

Enter a server only when you intentionally want a separate broker. When this field is set, the MQTT port, username and password fields are used as manual settings.

### Polling interval

The default is 5 seconds. Valid values are 2–3600 seconds.

## What happens when something goes wrong

- **USB unplugged:** the serial stream exits, the app waits a few seconds, then looks for the counter and reconnects.
- **Counter stops answering:** the current transaction is retried. If it still cannot be completed, the stream is closed and reconnected instead of publishing partial data.
- **MQTT temporarily unavailable:** serial readings continue and the app keeps trying to publish. Warnings are rate-limited so the log does not fill every few seconds.
- **Home Assistant MQTT credentials change:** automatic MQTT mode asks Supervisor for fresh service credentials and retries.
- **App process stops:** the Supervisor watchdog can restart the app.

## Troubleshooting

### No compatible GMC counter is available

Check that the counter is powered, connected by USB, and supported by the RFC1201 path. If `auto` cannot find it, try selecting its serial path explicitly and, if known, set the baud rate explicitly.

### More than one compatible GMC counter was found

Choose the intended serial device in the app configuration. The app deliberately will not pick one at random.

### Incomplete response / serial connection lost

The app received fewer bytes than the command requires. It will not publish that partial reading. If the problem persists, check the USB cable, counter, baud setting and whether another program is trying to use the same serial port.

### MQTT publish failed

In automatic mode, make sure an MQTT service provider such as the Home Assistant Mosquitto app is installed and running. In manual mode, recheck the broker address and credentials.

## Supported protocol boundary

This release expects RFC1201-style two-byte `GETCPM` data. It is not for GMC-500/500+/600/600+ RFC1801 counters or other newer protocol families with different reply formats.
