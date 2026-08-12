# GMC3xx Radiation Monitor

Reads supported GQ GMC-280/300/300E/300E Plus/320-family Geiger counters over USB and publishes their readings to MQTT.

The app is designed to be left alone once it is running:

- automatic serial-device discovery when `port` is `auto`;
- automatic baud detection;
- automatic Home Assistant MQTT service credentials when the MQTT server override is blank;
- one persistent serial connection while readings are flowing;
- automatic reconnect after USB/serial failure;
- bounded exact-length serial reads, so incomplete replies are dropped rather than decoded as CPM;
- no arbitrary upper CPM filter;
- Supervisor watchdog support;
- the historical serial-derived MQTT topic is kept for existing Home Assistant setups.

If you are replacing another GMC reader, stop the old reader before starting this one. Two programs must not use the same serial device at once.

Open the **Documentation** tab for the setup and migration guide.
