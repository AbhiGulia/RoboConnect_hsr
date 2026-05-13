"""Storage for saved locations."""

from __future__ import annotations

import json
import os
import threading

import rospy


class LocationStore:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = threading.Lock()
        self.locations = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError) as exc:
            rospy.logwarn("Failed to load saved locations (%s). Starting with empty list.", exc)
            return {}

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as handle:
            json.dump(self.locations, handle, indent=2)
        os.chmod(self.filepath, 0o600)

    def save(self, name: str, x: float, y: float, yaw: float) -> None:
        with self._lock:
            self.locations[name] = {"x": x, "y": y, "yaw": yaw}
            self._persist()
        rospy.loginfo("Saved location '%s': (%.2f, %.2f, yaw=%.2f)", name, x, y, yaw)

    def get(self, name: str) -> dict | None:
        with self._lock:
            return self.locations.get(name)

    def names(self) -> list[str]:
        with self._lock:
            return list(self.locations.keys())


__all__ = ["LocationStore"]
