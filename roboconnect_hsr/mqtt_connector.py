"""MQTT connector with reconnect and TLS/WSS support."""

from __future__ import annotations

import threading
import time

import paho.mqtt.client as mqtt
import rospy

from .config import RobotConfig


class MqttConnector:
    def __init__(self, config: RobotConfig, client_id: str, availability_topic: str | None = None):
        self.config = config
        self.client_id = client_id
        self.availability_topic = availability_topic
        self.connected = False
        self._connected_event = threading.Event()
        self._lock = threading.Lock()
        self._subscriptions: dict[str, tuple[int, callable]] = {}
        self._shutdown = False

        transport = "websockets" if self.config.protocol == "wss" else "tcp"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=self.client_id, transport=transport)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        if self.config.auth_enabled and self.config.username:
            self.client.username_pw_set(self.config.username, self.config.password or "")

        if self.config.protocol in {"ssl", "wss"}:
            self.client.tls_set()
            if self.config.protocol == "wss":
                self.client.ws_set_options(path="/")

        if self.availability_topic:
            self.client.will_set(self.availability_topic, payload="offline", qos=1, retain=True)

    def connect(self, retries: int = 5, timeout: float = 5.0) -> bool:
        self.client.loop_start()
        for attempt in range(1, retries + 1):
            try:
                self.client.connect(self.config.host, self.config.port, 60)
            except Exception as exc:
                rospy.logwarn("MQTT connect attempt %d failed: %s", attempt, exc)
                self._sleep_backoff(attempt)
                continue

            if self._connected_event.wait(timeout):
                return True

            self.client.disconnect()
            self._connected_event.clear()
            rospy.logwarn("MQTT connection attempt %d timed out.", attempt)
            self._sleep_backoff(attempt)

        rospy.logerr("MQTT connection failed after retries.")
        return False

    def disconnect(self) -> None:
        self._shutdown = True
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False) -> None:
        if not self.connected:
            return
        try:
            self.client.publish(topic, payload, qos=qos, retain=retain)
        except Exception as exc:
            rospy.logwarn("MQTT publish failed for %s: %s", topic, exc)

    def subscribe(self, topic: str, callback, qos: int = 2) -> None:
        with self._lock:
            self._subscriptions[topic] = (qos, callback)
        self.client.subscribe(topic, qos=qos)
        self.client.message_callback_add(topic, callback)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self._connected_event.set()
            rospy.loginfo("MQTT connected.")
            self._resubscribe()
        else:
            rospy.logerr("MQTT connection failed with code %s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        self._connected_event.clear()
        if self._shutdown:
            return
        rospy.logwarn("MQTT disconnected (code %s), retrying.", rc)
        threading.Thread(target=self._reconnect_loop, daemon=True).start()

    def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._shutdown:
            attempt += 1
            try:
                self.client.reconnect()
                if self._connected_event.wait(5.0):
                    return
            except Exception as exc:
                rospy.logwarn("MQTT reconnect attempt %d failed: %s", attempt, exc)
            self._sleep_backoff(attempt)

    def _resubscribe(self) -> None:
        with self._lock:
            subscriptions = list(self._subscriptions.items())
        for topic, (qos, callback) in subscriptions:
            self.client.subscribe(topic, qos=qos)
            self.client.message_callback_add(topic, callback)

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(30.0, 2 ** attempt))


def test_connection(config: RobotConfig, client_id: str, timeout: float = 5.0) -> bool:
    connector = MqttConnector(config, client_id)
    try:
        success = connector.connect(retries=1, timeout=timeout)
    finally:
        connector.disconnect()
    return success


__all__ = ["MqttConnector", "test_connection"]
