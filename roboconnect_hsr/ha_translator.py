"""Home Assistant translator with Temi-style discovery."""

from __future__ import annotations

import json

from .device_base import DeviceTranslator


class EntityConfig:
    def __init__(
        self,
        name: str,
        unique_id: str,
        platform: str,
        command_topic: str | None = None,
        state_topic: str | None = None,
        availability_topic: str | None = None,
        qos: int = 1,
        retain: bool = False,
        **kwargs,
    ):
        self.name = name
        self.unique_id = unique_id
        self.platform = platform
        self.command_topic = command_topic
        self.state_topic = state_topic
        self.availability_topic = availability_topic
        self.qos = qos
        self.retain = retain
        self.extra = kwargs


class EntityRegistry:
    def __init__(self):
        self.configs: dict[str, EntityConfig] = {}

    def build_default_entities(self) -> None:
        self.configs["location"] = EntityConfig(
            name="Location",
            unique_id="location",
            platform="select",
            command_topic="set",
            state_topic="state",
            options=[],
        )

        self.configs["save_location"] = EntityConfig(
            name="Save Location",
            unique_id="save_location",
            platform="button",
            command_topic="set",
            payload_press="PRESS",
        )

        self.configs["location_name_input"] = EntityConfig(
            name="Location Name",
            unique_id="location_name_input",
            platform="text",
            command_topic="set",
            mode="text",
        )

        self.configs["speak"] = EntityConfig(
            name="Speak",
            unique_id="speak",
            platform="text",
            command_topic="set",
            state_topic="state",
            mode="text",
        )

        self.configs["announce"] = EntityConfig(
            name="Announce",
            unique_id="announce",
            platform="text",
            command_topic="set",
            state_topic="state",
            mode="text",
        )

        self.configs["gripper"] = EntityConfig(
            name="Gripper",
            unique_id="gripper",
            platform="switch",
            command_topic="set",
            state_topic="state",
            payload_on="close",
            payload_off="open",
            state_on="closed",
            state_off="open",
        )

        self.configs["suction"] = EntityConfig(
            name="Suction",
            unique_id="suction",
            platform="switch",
            command_topic="set",
            state_topic="state",
            payload_on="on",
            payload_off="off",
        )

        self.configs["dock"] = EntityConfig(
            name="Dock",
            unique_id="dock",
            platform="button",
            command_topic="set",
            payload_press="PRESS",
        )

        self.configs["serial_execution"] = EntityConfig(
            name="Serial Execution",
            unique_id="serial_execution",
            platform="switch",
            command_topic="set",
            state_topic="state",
            payload_on="ON",
            payload_off="OFF",
        )

        self.configs["position_x"] = EntityConfig(
            name="Position X",
            unique_id="position_x",
            platform="sensor",
            state_topic="state",
            unit_of_measurement="m",
        )

        self.configs["position_y"] = EntityConfig(
            name="Position Y",
            unique_id="position_y",
            platform="sensor",
            state_topic="state",
            unit_of_measurement="m",
        )

        self.configs["busy"] = EntityConfig(
            name="Robot Busy",
            unique_id="busy",
            platform="binary_sensor",
            state_topic="state",
            payload_on="ON",
            payload_off="OFF",
        )

        self.configs["emergency"] = EntityConfig(
            name="Emergency Stop",
            unique_id="emergency",
            platform="button",
            command_topic="set",
            payload_press="STOP",
        )

    def update_location_options(self, options: list[str]) -> None:
        if "location" in self.configs:
            self.configs["location"].extra["options"] = options


class HomeAssistantTranslator(DeviceTranslator):
    def __init__(
        self,
        connector,
        registry: EntityRegistry,
        device_id: str,
        base_topic: str,
        availability_topic: str,
        device_name: str,
    ):
        self.connector = connector
        self.registry = registry
        self.device_id = device_id
        self.base_topic = base_topic
        self.availability_topic = availability_topic
        self.device_name = device_name

    def _topic_base(self, cfg: EntityConfig) -> str:
        unique = f"{self.device_id}_--_{cfg.unique_id}"  # Temi-style delimiter for compatibility
        return f"{self.base_topic}/{cfg.platform}/{unique}"

    def publish_discovery(self) -> None:
        device_info = {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "mf": "Toyota",
            "mdl": "HSR",
            "sw": "ROS 1",
            "hw": "1.0",
        }
        for cfg in self.registry.configs.values():
            base = self._topic_base(cfg)
            payload = {
                "~": base,
                "name": cfg.name,
                "uniq_id": f"{self.device_id}_--_{cfg.unique_id}",
                "dev": device_info,
                "qos": cfg.qos,
                "retain": cfg.retain,
                "avty_t": self.availability_topic,
            }
            if cfg.state_topic:
                payload["stat_t"] = f"~/{cfg.state_topic}"
            if cfg.command_topic:
                payload["cmd_t"] = f"~/{cfg.command_topic}"
            payload.update(cfg.extra)
            self.connector.publish(f"{base}/config", json.dumps(payload), retain=True)

    def publish_state(self, uid: str, value: str) -> None:
        cfg = self.registry.configs.get(uid)
        if not cfg or not cfg.state_topic:
            return
        topic = f"{self._topic_base(cfg)}/{cfg.state_topic}"
        self.connector.publish(topic, str(value), qos=cfg.qos, retain=cfg.retain)

    def subscribe_all_commands(self, callback) -> None:
        for cfg in self.registry.configs.values():
            if cfg.command_topic:
                topic = f"{self._topic_base(cfg)}/{cfg.command_topic}"
                self.connector.subscribe(topic, callback)

    def command_topics(self) -> dict[str, str]:
        topics: dict[str, str] = {}
        for uid, cfg in self.registry.configs.items():
            if cfg.command_topic:
                topics[f"{self._topic_base(cfg)}/{cfg.command_topic}"] = uid
        return topics


__all__ = ["EntityConfig", "EntityRegistry", "HomeAssistantTranslator"]
