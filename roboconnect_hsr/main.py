"""Main RoboConnect-HSR node."""

from __future__ import annotations

import os

import rospy

from .action_manager import HSRActionManager
from .autostart import AutostartManager
from .config import ConfigStore, SetupWizard
from .ha_translator import EntityRegistry, HomeAssistantTranslator
from .mqtt_connector import MqttConnector
from .storage import LocationStore
from .task_executor import TaskExecutor

MQTT_BASE_TOPIC = "homeassistant"


class RoboConnectHSR:
    def __init__(self):
        config_store = ConfigStore()
        config = config_store.load()
        if config is None:
            config = SetupWizard(config_store).run(AutostartManager())

        rospy.init_node("roboconnect_hsr", anonymous=True)

        registry = EntityRegistry()
        registry.build_default_entities()

        location_path = os.path.join(config_store.data_dir, "saved_locations.json")
        self.location_store = LocationStore(location_path)
        registry.update_location_options(self.location_store.names())

        availability_topic = f"{MQTT_BASE_TOPIC}/{config.device_id}/availability"

        self.connector = MqttConnector(config, config.device_id, availability_topic=availability_topic)
        self.action_mgr = HSRActionManager(self.location_store)
        self.translator = HomeAssistantTranslator(
            self.connector,
            registry,
            config.device_id,
            MQTT_BASE_TOPIC,
            availability_topic,
            config.robot_name,
        )
        self.executor = TaskExecutor(self.action_mgr, self.translator)
        self.command_topics = self.translator.command_topics()

        if not self.connector.connect():
            raise RuntimeError("Unable to connect to MQTT broker.")

        self.translator.publish_discovery()
        self.translator.subscribe_all_commands(self._on_mqtt_command)

        rospy.Timer(rospy.Duration(5), self._publish_telemetry)
        self.translator.publish_state("busy", "OFF")
        self.executor.set_serial_execution(True)

        self.connector.publish(availability_topic, "online", qos=1, retain=True)
        rospy.loginfo("RoboConnect-HSR ready.")
        rospy.on_shutdown(self.shutdown)

    def _on_mqtt_command(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8").strip()
        rospy.loginfo("MQTT command: %s -> %s", msg.topic, payload)

        uid = self.command_topics.get(msg.topic)
        if not uid:
            return

        if uid == "location":
            self.executor.enqueue("go_to_location", payload)
        elif uid == "speak":
            self.executor.enqueue("speak", payload)
        elif uid == "announce":
            self.executor.enqueue("announce", payload)
        elif uid == "save_location":
            self.action_mgr.speak("What should I name this location?", wait=False)
        elif uid == "location_name_input":
            name = payload.strip()
            if name:
                x, y, yaw = self.action_mgr.get_current_pose()
                self.location_store.save(name, x, y, yaw)
                self.translator.registry.update_location_options(self.location_store.names())
                self.translator.publish_discovery()
                self.action_mgr.speak(f"Location {name} saved.", wait=False)
        elif uid == "gripper":
            self.executor.enqueue("gripper", payload)
        elif uid == "suction":
            self.executor.enqueue("suction", payload)
        elif uid == "dock":
            self.executor.enqueue("dock", None)
        elif uid == "emergency":
            self.executor.enqueue("emergency", None, emergency=True)
        elif uid == "serial_execution":
            self.executor.enqueue("serial_execution", payload)

    def _publish_telemetry(self, event):
        if self.action_mgr.current_pose is not None:
            pose = self.action_mgr.current_pose.pose.position
            self.translator.publish_state("position_x", f"{pose.x:.3f}")
            self.translator.publish_state("position_y", f"{pose.y:.3f}")
        busy = not self.executor.queue.empty() or self.action_mgr.abort_current
        self.translator.publish_state("busy", "ON" if busy else "OFF")

    def shutdown(self):
        self.connector.publish(self.connector.availability_topic, "offline", qos=1, retain=True)
        self.connector.disconnect()


def main():
    RoboConnectHSR()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
