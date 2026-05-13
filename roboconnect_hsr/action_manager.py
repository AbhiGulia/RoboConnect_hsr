"""Action manager for HSR operations."""

from __future__ import annotations

import rospy
import actionlib
from std_msgs.msg import Bool
from geometry_msgs.msg import Twist, PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
import tf.transformations

from tmc_msgs.msg import TalkRequestAction, TalkRequestGoal, Voice
from tmc_suction.msg import SuctionControlAction, SuctionControlGoal
from tmc_control_msgs.msg import GripperApplyEffortAction, GripperApplyEffortGoal
from hsrb_autocharge.msg import DockChargeStationAction, DockChargeStationGoal


class HSRActionManager:
    def __init__(self, location_store):
        self.location_store = location_store
        self.abort_current = False

        self.move_base_client = actionlib.SimpleActionClient("move_base/move", MoveBaseAction)
        self.tts_client = actionlib.SimpleActionClient("/talk_request_action", TalkRequestAction)
        self.suction_client = actionlib.SimpleActionClient("/hsrb/suction_control", SuctionControlAction)
        self.gripper_client = actionlib.SimpleActionClient("/hsrb/gripper_controller/grasp", GripperApplyEffortAction)
        self.dock_client = actionlib.SimpleActionClient("/hsrb/autocharge_node/dock", DockChargeStationAction)

        rospy.loginfo("Waiting for action servers...")
        self._wait_for_server(self.move_base_client, "move_base/move")
        self._wait_for_server(self.tts_client, "/talk_request_action")
        self._wait_for_server(self.suction_client, "/hsrb/suction_control")
        self._wait_for_server(self.gripper_client, "/hsrb/gripper_controller/grasp")
        self._wait_for_server(self.dock_client, "/hsrb/autocharge_node/dock")

        self.current_pose = None
        rospy.Subscriber("/global_pose", PoseStamped, self._pose_cb)

    @staticmethod
    def _wait_for_server(client, name: str, timeout: float = 5.0, retries: int = 3) -> None:
        for attempt in range(1, retries + 1):
            if client.wait_for_server(rospy.Duration(timeout)):
                return
            rospy.logwarn("Action server %s not ready (attempt %d/%d)", name, attempt, retries)
        raise RuntimeError(f"Action server {name} unavailable after retries.")

    def _pose_cb(self, msg):
        self.current_pose = msg

    def get_current_pose(self):
        if self.current_pose is None:
            return 0.0, 0.0, 0.0
        pose = self.current_pose.pose
        q = pose.orientation
        _, _, yaw = tf.transformations.euler_from_quaternion([q.x, q.y, q.z, q.w])
        return pose.position.x, pose.position.y, yaw

    def _make_tts_goal(self, text: str, is_parallel: bool) -> TalkRequestGoal:
        goal = TalkRequestGoal()
        goal.data = Voice()
        goal.data.sentence = text
        goal.data.language = Voice.kEnglish
        goal.data.interrupting = is_parallel
        goal.data.queueing = not is_parallel
        return goal

    @staticmethod
    def _make_suction_goal(on: bool) -> SuctionControlGoal:
        goal = SuctionControlGoal()
        goal.suction_on = Bool(data=on)
        return goal

    @staticmethod
    def _make_gripper_goal(close: bool) -> GripperApplyEffortGoal:
        goal = GripperApplyEffortGoal()
        goal.effort = -0.1 if close else 0.1
        goal.do_control_stop = close
        return goal

    @staticmethod
    def _make_dock_goal() -> DockChargeStationGoal:
        return DockChargeStationGoal()

    def go_to_location(self, name: str, wait: bool = True) -> bool:
        coords = self.location_store.get(name)
        if coords is None:
            rospy.logerr("Location '%s' not found", name)
            return False

        rospy.loginfo("Navigating to %s via move_base...", name)
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = coords["x"]
        goal.target_pose.pose.position.y = coords["y"]

        quat = tf.transformations.quaternion_from_euler(0, 0, coords["yaw"])
        goal.target_pose.pose.orientation.x = quat[0]
        goal.target_pose.pose.orientation.y = quat[1]
        goal.target_pose.pose.orientation.z = quat[2]
        goal.target_pose.pose.orientation.w = quat[3]

        self.move_base_client.send_goal(goal)

        if not wait:
            return True

        goal_timeout = 120
        pos_tol = 0.25
        yaw_tol = 0.26

        start = rospy.Time.now()
        rate = rospy.Rate(10)

        while not rospy.is_shutdown():
            if self.abort_current:
                self.move_base_client.cancel_goal()
                return False

            state = self.move_base_client.get_state()
            if state == actionlib.GoalStatus.SUCCEEDED:
                return True
            if state in [
                actionlib.GoalStatus.ABORTED,
                actionlib.GoalStatus.REJECTED,
                actionlib.GoalStatus.PREEMPTED,
            ]:
                return False

            x, y, yaw = self.get_current_pose()
            dx = x - coords["x"]
            dy = y - coords["y"]
            dist = (dx**2 + dy**2) ** 0.5
            dyaw = abs((yaw - coords["yaw"] + 3.14159) % (2 * 3.14159) - 3.14159)

            if dist < pos_tol and dyaw < yaw_tol:
                self.move_base_client.cancel_goal()
                return True

            if (rospy.Time.now() - start).to_sec() > goal_timeout:
                self.move_base_client.cancel_goal()
                return False

            rate.sleep()

        return self.move_base_client.get_state() == actionlib.GoalStatus.SUCCEEDED

    def speak(self, text: str, wait: bool = True) -> bool:
        goal = self._make_tts_goal(text, is_parallel=not wait)
        self.tts_client.send_goal(goal)
        if not wait:
            return True

        rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            if self.abort_current:
                self.tts_client.cancel_goal()
                return False

            state = self.tts_client.get_state()
            if state == actionlib.GoalStatus.SUCCEEDED:
                return True
            if state in [
                actionlib.GoalStatus.ABORTED,
                actionlib.GoalStatus.REJECTED,
                actionlib.GoalStatus.PREEMPTED,
            ]:
                return False

            rate.sleep()
        return self.tts_client.get_state() == actionlib.GoalStatus.SUCCEEDED

    def set_gripper(self, close: bool) -> bool:
        goal = self._make_gripper_goal(close)
        self.gripper_client.send_goal(goal)
        self.gripper_client.wait_for_result(rospy.Duration(10))
        return self.gripper_client.get_state() == actionlib.GoalStatus.SUCCEEDED

    def set_suction(self, on: bool) -> bool:
        goal = self._make_suction_goal(on)
        self.suction_client.send_goal(goal)
        self.suction_client.wait_for_result(rospy.Duration(5))
        return self.suction_client.get_state() == actionlib.GoalStatus.SUCCEEDED

    def dock(self) -> bool:
        self.dock_client.send_goal(self._make_dock_goal())
        self.dock_client.wait_for_result(rospy.Duration(10))
        return self.dock_client.get_state() == actionlib.GoalStatus.SUCCEEDED

    def emergency_stop(self) -> None:
        self.abort_current = True
        vel_pub = rospy.Publisher("/hsrb/command_velocity", Twist, queue_size=1)
        vel_pub.publish(Twist())

        self.move_base_client.cancel_all_goals()
        self.tts_client.cancel_all_goals()
        self.suction_client.cancel_all_goals()
        self.gripper_client.cancel_all_goals()
        self.dock_client.cancel_all_goals()
        rospy.logwarn("Emergency Stop: All actions canceled.")


__all__ = ["HSRActionManager"]
