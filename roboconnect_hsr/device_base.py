"""Abstract device translator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class DeviceTranslator(ABC):
    @abstractmethod
    def publish_discovery(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish_state(self, uid: str, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe_all_commands(self, callback: Callable) -> None:
        raise NotImplementedError

    @abstractmethod
    def command_topics(self) -> dict[str, str]:
        raise NotImplementedError


__all__ = ["DeviceTranslator"]
