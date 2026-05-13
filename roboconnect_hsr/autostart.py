"""Systemd autostart helper."""

from __future__ import annotations

import os
import subprocess
import sys


class AutostartManager:
    def __init__(self, service_name: str = "roboconnect_hsr"):
        self.service_name = service_name

    def install(self) -> bool:
        service_dir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(service_dir, exist_ok=True)
        service_path = os.path.join(service_dir, f"{self.service_name}.service")
        exec_cmd = f"{sys.executable} -m roboconnect_hsr.main"
        working_dir = os.getcwd()

        service_body = "\n".join(
            [
                "[Unit]",
                "Description=RoboConnect HSR MQTT bridge",
                "After=network-online.target",
                "",
                "[Service]",
                "Type=simple",
                f"WorkingDirectory={working_dir}",
                f"ExecStart={exec_cmd}",
                "Restart=always",
                "RestartSec=5",
                "",
                "[Install]",
                "WantedBy=default.target",
                "",
            ]
        )

        with open(service_path, "w", encoding="utf-8") as handle:
            handle.write(service_body)

        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", "--now", f"{self.service_name}.service"], check=True)
            print("Autostart enabled via systemd user service.")
            return True
        except (OSError, subprocess.CalledProcessError):
            print("Autostart service created at:", service_path)
            print("Run: systemctl --user daemon-reload")
            print(f"Run: systemctl --user enable --now {self.service_name}.service")
            return False


__all__ = ["AutostartManager"]
