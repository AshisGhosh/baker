#!/usr/bin/env python

import behavior_container
import rospy
import actionlib

from geometry_msgs.msg import Quaternion
from move_base_behavior import MoveBaseBehavior
from ipa_manipulation_msgs.msg import MoveToAction, MoveToGoal
import services_params as srv
from tf.transformations import quaternion_from_euler

class TrashcanEmptyingBehavior(behavior_container.BehaviorContainer):

	# ========================================================================
	# Description:
	# Class which contains the behavior of trashcan emptying
	# > Go to the trashcan
	# > Take the trashcan
	# > Go to the trolley
	# > Empty the trashcan
	# > Go to the trashcan location
	# > Leave the trashcan
	# ========================================================================

	def __init__(self, behavior_name, interrupt_var, move_base_service_str):
		super(TrashcanEmptyingBehavior, self).__init__(behavior_name, interrupt_var)
		self.move_base_handler_ = MoveBaseBehavior("MoveBaseBehavior", self.interrupt_var_, move_base_service_str)
		(self.trolley_position_, self.trashcan_position_) = (None, None)

		self.catch_trashcan_service_str_ = srv.CATCH_TRASHCAN_SERVICE_STR
		self.empty_trashcan_service_str_ = srv.EMPTY_TRASHCAN_SERVICE_STR
		self.leave_trashcan_service_str_ = srv.LEAVE_TRASHCAN_SERVICE_STR
		self.transport_position_service_str_ = srv.TRANSPORT_POSITION_STR
		self.rest_position_service_str_ = srv.REST_POSITION_STR

	# Method for setting parameters for the behavior
	def setParameters(self, trashcan_pose, trolley_position):
		self.trashcan_pose_ = trashcan_pose
		self.trolley_position_ = trolley_position

	# Method for returning to the standard pose of the robot
	def returnToRobotStandardState(self):
		# save current data if necessary
		# undo or check whether everything has been undone
		pass

	def moveToGoal(self, goal):
		self.move_base_handler_.setParameters(
			goal_position=goal,
			goal_orientation=Quaternion(x=0., y=0., z=0., w=1.),
			header_frame_id='base_link'
		)
		self.move_base_handler_.executeBehavior()

	def catchTrashcan(self):
		return self.executeAction(self.catch_trashcan_service_str_, position=[0.75,-0.60, 0.505], rotation=[0.0, 0.0, 3.92])

	def executeAction(self, action_name, target_pose=None):

		goal = MoveToGoal()
		if target_pose is not None:
			goal = MoveToGoal()
			goal.target_pos.pose = target_pose

		client = actionlib.SimpleActionClient(action_name, MoveToAction)
		client.wait_for_server()
		client.send_goal(goal)
		client.wait_for_result()
		return client.get_result()

	def emptyTrashcan(self):
		return self.executeAction(self.empty_trashcan_service_str_, self.trashcan_pose_) # todo rmb-ma (not trashcan position)

	def leaveTrashcan(self):
		return self.executeAction(self.leave_trashcan_service_str_, self.trashcan_pose_)

	def transportPosition(self):
		return self.executeAction(self.transport_position_service_str_)

	def restPosition(self):
		return self.executeAction(self.rest_position_service_str_)

	# Implemented Behavior
	def executeCustomBehavior(self):
		assert(self.trashcan_pose_ is not None and self.trolley_position_ is not None)

		self.printMsg("Executing trashcan behavior located on ({}, {})".format(self.trashcan_pose_.x, self.trashcan_pose_.y))

		# todo (rmb-ma): see how we can go there + see the locations to clean it

		self.printMsg("> Moving to the trashcan")
		self.moveToGoal(self.trashcan_position_)
		if self.move_base_handler_.failed():
			self.printMsg('Trashcan is not accessible. Failed to for emptying trashcan ({}, {})'.format(self.trashcan_position_.x, self.trashcan_position_.y))
			self.state_ = 4
			return
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Todo. Take the trashcan")
		self.catchTrashcan()
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Going to transport position")
		self.transportPosition()
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Moving to the trolley located on ({}, {})".format(self.trolley_position_.x, self.trolley_position_.y))
		self.moveToGoal(self.trolley_position_)
		if self.move_base_handler_.failed():
			self.printMsg('Trolley is not accessible. Failed to for emptying trashcan ({}, {})'.format(self.trashcan_position_.x, self.trashcan_position_.y))
			self.state_ = 4
			return
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Todo. Empty the trashcan")
		self.emptyTrashcan()
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Going to transport position")
		self.transportPosition()
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Going to the trashcan location")
		self.moveToGoal(self.trashcan_position_)
		if self.handleInterrupt() >= 1:
			return
		if self.move_base_handler_.failed():
			self.printMsg('Trashcan location is not accessible. Failed to for emptying trashcan ({}, {})'.format(self.trashcan_position_.x, self.trashcan_position_.y))
			self.state_ = 4
			return

		self.printMsg("> Todo. Leave the trashcan")
		self.leaveTrashcan()
		if self.handleInterrupt() >= 1:
			return

		self.printMsg("> Going to rest position")
		self.restPosition()
		if self.handleInterrupt() >= 1:
			return
