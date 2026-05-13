"""Configuration and first-run setup utilities."""

from __future__ import annotations

from dataclasses import dataclass
import getpass
import json
import os

CONFIG_VERSION = 1
DEFAULT_DATA_DIR = os.path.expanduser("~/.roboconnect_hsr")


def normalize_name(name: str) -> str:
    return name.strip().replace(" ", "_")


@dataclass
class RobotConfig:
    robot_name: str
    protocol: str
    host: str
    port: int
    auth_enabled: bool
    username: str | None = None
    password: str | None = None

    @property
    def device_id(self) -> str:
        return normalize_name(self.robot_name)

    def to_dict(self) -> dict:
        return {
            "version": CONFIG_VERSION,
            "robot_name": self.robot_name,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "auth_enabled": self.auth_enabled,
            "username": self.username,
            "password": self.password,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RobotConfig":
        return cls(
            robot_name=str(payload["robot_name"]),
            protocol=str(payload["protocol"]).lower(),
            host=str(payload["host"]),
            port=int(payload["port"]),
            auth_enabled=bool(payload.get("auth_enabled", False)),
            username=payload.get("username"),
            password=payload.get("password"),
        )


class ConfigStore:
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self.data_dir = data_dir
        self.path = os.path.join(self.data_dir, "config.json")

    def load(self) -> RobotConfig | None:
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return RobotConfig.from_dict(payload)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, config: RobotConfig) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.chmod(self.data_dir, 0o700)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(config.to_dict(), handle, indent=2)
        os.chmod(self.path, 0o600)


class SetupWizard:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store

    def run(self, autostart_manager=None) -> RobotConfig:
        print("RoboConnect-HSR first-time setup")
        robot_name = self._prompt_non_empty("Robot name: ")
        protocol = self._prompt_protocol()
        host = self._prompt_non_empty("MQTT broker host/IP: ")
        port = self._prompt_port("MQTT broker port: ")

        auth_enabled = False
        username = None
        password = None
        if protocol == "tcp":
            auth_enabled = self._prompt_yes_no("Enable authentication? [y/N]: ", default=False)
            if auth_enabled:
                username = self._prompt_non_empty("Username: ")
                password = getpass.getpass("Password: ")

        config = RobotConfig(
            robot_name=robot_name,
            protocol=protocol,
            host=host,
            port=port,
            auth_enabled=auth_enabled,
            username=username,
            password=password,
        )
        self.config_store.save(config)

        if self._prompt_yes_no("Test MQTT connection now? [Y/n]: ", default=True):
            if not self._test_connection(config):
                raise RuntimeError("MQTT connection failed during setup.")
            print("Connection successful.")

        if autostart_manager and self._prompt_yes_no("Enable autostart on boot? [y/N]: ", default=False):
            autostart_manager.install()

        return config

    def _test_connection(self, config: RobotConfig) -> bool:
        from .mqtt_connector import test_connection

        while True:
            if test_connection(config, config.device_id):
                return True
            retry = self._prompt_yes_no("Connection failed. Retry? [y/N]: ", default=False)
            if not retry:
                return False

    @staticmethod
    def _prompt_non_empty(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value

    @staticmethod
    def _prompt_port(prompt: str) -> int:
        while True:
            value = input(prompt).strip()
            if value.isdigit():
                port = int(value)
                if 1 <= port <= 65535:
                    return port
            print("Please enter a valid port number (1-65535).")

    @staticmethod
    def _prompt_protocol() -> str:
        options = {"1": "tcp", "2": "ssl", "3": "wss"}
        while True:
            print("Select MQTT protocol:")
            print("  1) tcp")
            print("  2) ssl (tls)")
            print("  3) wss")
            choice = input("Choice: ").strip()
            if choice in options:
                return options[choice]
            print("Please select 1, 2, or 3.")

    @staticmethod
    def _prompt_yes_no(prompt: str, default: bool) -> bool:
        while True:
            value = input(prompt).strip().lower()
            if not value:
                return default
            if value in {"y", "yes"}:
                return True
            if value in {"n", "no"}:
                return False


__all__ = ["ConfigStore", "RobotConfig", "SetupWizard", "normalize_name"]
