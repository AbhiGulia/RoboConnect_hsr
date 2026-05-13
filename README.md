# RoboConnect_hsr

MQTT smart-home bridge for Toyota HSR using ROS 1 actions and Home Assistant discovery.

## Quick start

1. Ensure ROS 1, `paho-mqtt`, and required HSR message packages are available in your environment.
2. Run the node:

```
python3 -m roboconnect_hsr.main
```

On first launch, a setup wizard asks for:
- Robot name
- MQTT protocol (tcp / tls(ssl) / wss)
- Broker host and port
- Authentication (tcp only)

The wizard stores configuration in `~/.roboconnect_hsr/config.json` with permissions set to `0600`, tests the MQTT connection, and can enable autostart.

Saved locations are stored alongside the config in `~/.roboconnect_hsr/saved_locations.json`.

## Autostart

The setup wizard can install a systemd user service. If you need to enable it manually:

```
systemctl --user daemon-reload
systemctl --user enable --now roboconnect_hsr.service
```

## Structure

- `roboconnect_hsr/mqtt_connector.py`: MQTT connection, retries, TLS/WSS
- `roboconnect_hsr/config.py`: setup wizard and secured configuration storage
- `roboconnect_hsr/storage.py`: saved location store
- `roboconnect_hsr/device_base.py`: translator interface
- `roboconnect_hsr/ha_translator.py`: Home Assistant discovery and topics
- `roboconnect_hsr/action_manager.py`: HSR action execution
- `roboconnect_hsr/task_executor.py`: task queue
- `roboconnect_hsr/main.py`: application wiring and ROS node
