"""Task queue and executor."""

from __future__ import annotations

import queue as queue_module
import threading
from typing import Any

import rospy


class Task:
    _seq = 0
    _lock = threading.Lock()

    def __init__(self, command: str, param: Any, priority: int = 0):
        self.command = command
        self.param = param
        self.priority = priority
        with Task._lock:
            self.seq = Task._seq
            Task._seq += 1

    def __lt__(self, other):
        if self.priority == other.priority:
            return self.seq < other.seq
        return self.priority > other.priority


class TaskExecutor:
    def __init__(self, action_mgr, translator):
        self.action = action_mgr
        self.translator = translator
        self.queue = queue_module.PriorityQueue()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

        self.serial_execution = True
        self.serial_execution_lock = threading.Lock()

    def set_serial_execution(self, enabled: bool) -> None:
        with self.serial_execution_lock:
            self.serial_execution = enabled
            rospy.loginfo("Serial execution: %s", "ON" if self.serial_execution else "OFF")
        self.translator.publish_state("serial_execution", "ON" if enabled else "OFF")

    def enqueue(self, command: str, param: Any, emergency: bool = False) -> None:
        task = Task(command, param, 10 if emergency else 0)
        self.queue.put(task)

    def has_pending_tasks(self) -> bool:
        return not self.queue.empty()

    def _run(self) -> None:
        while True:
            task = self.queue.get()
            try:
                self._execute_single(task)
            except Exception as exc:
                rospy.logerr("Task %s(%s) failed: %s", task.command, task.param, exc)

    def _execute_single(self, task: Task) -> None:
        cmd = task.command
        param = task.param

        if cmd == "serial_execution":
            self.set_serial_execution(str(param).upper() == "ON")
            return

        with self.serial_execution_lock:
            wait = self.serial_execution

        if cmd == "go_to_location":
            if wait:
                result = self.action.go_to_location(param, wait=True)
                self.translator.publish_state("location", param if result else "failed")
            else:
                self.action.go_to_location(param, wait=False)
        elif cmd == "speak":
            if wait:
                result = self.action.speak(param, wait=True)
                self.translator.publish_state("speak", param if result else "aborted")
            else:
                self.action.speak(param, wait=False)
        elif cmd == "announce":
            self.action.speak(param, wait=False)
            self.translator.publish_state("announce", param)
        elif cmd == "gripper":
            close = str(param).lower() == "close"
            self.action.set_gripper(close)
            self.translator.publish_state("gripper", "closed" if close else "open")
        elif cmd == "suction":
            on = str(param).lower() == "on"
            self.action.set_suction(on)
            self.translator.publish_state("suction", "on" if on else "off")
        elif cmd == "dock":
            self.action.dock()
        elif cmd == "emergency":
            self.action.emergency_stop()


__all__ = ["Task", "TaskExecutor"]
