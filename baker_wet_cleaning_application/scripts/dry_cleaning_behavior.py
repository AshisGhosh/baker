#!/usr/bin/env python

from threading import Lock, Thread

import rospy
from cob_object_detection_msgs.msg import DetectionArray
from geometry_msgs.msg import Pose2D, Quaternion
from std_srvs.srv import Empty

import move_base_behavior
import move_base_path_behavior
import room_exploration_behavior
import services_params as srv
import tool_changing_behavior
import trolley_movement_behavior
from dirt_removing_behavior import DirtRemovingBehavior
import behavior_container
from trashcan_emptying_behavior import TrashcanEmptyingBehavior


class DryCleaningBehavior(behavior_container.BehaviorContainer):

	#========================================================================
	# Description:
	# Handles the dry cleaning process (i.e. Exploring, Dirt removal, Trashcan)
	# for all rooms provided in a given list
	#========================================================================
	@staticmethod
	def containsTrashcanTask(tasks):
		return -1 in tasks


	@staticmethod
	def containsDirtTask(tasks):
		return 0 in tasks


	@staticmethod
	def fakeDetectionLocator(path_position):
		location = (path_position.x, path_position.y)
		return location

	def __init__(self, behavior_name, interrupt_var):
		super(DryCleaningBehavior, self).__init__(behavior_name, interrupt_var)
		self.path_follower_ = None
		self.detected_dirt_ = None
		self.detected_trash_= None
		self.local_mutex_ = Lock()
		(self.trash_topic_subscriber_, self.dirt_topic_subscriber_) = (None, None)
		(self.found_dirtspots_, self.found_trashcans_) = (0, 0)

	# Method for setting parameters for the behavior
	def setParameters(self, database_handler, sequencing_result, mapping, robot_radius, coverage_radius, field_of_view,
					  field_of_view_origin, room_information_in_meter):
		self.database_handler_ = database_handler
		self.sequencing_result_ = sequencing_result
		self.mapping_ = mapping
		self.room_exploration_service_str_ = srv.ROOM_EXPLORATION_SERVICE_STR
		self.move_base_path_service_str_ = srv.MOVE_BASE_PATH_SERVICE_STR

		self.robot_radius_ = robot_radius
		self.coverage_radius_ = coverage_radius
		self.field_of_view_ = field_of_view  # this field of view represents the off-center iMop floor wiping device
		self.field_of_view_origin_ = field_of_view_origin
		self.room_information_in_meter_ = room_information_in_meter


	# Method for returning to the standard state of the robot
	def returnToRobotStandardState(self):
		# nothing to be saved
		# nothing to be undone
		pass


	# Empty the trash detected in self.detected_trash_
	def trashcanRoutine(self, room_id):
		if self.detected_trash_ is None:
			assert False

		self.found_trashcans_ += 1
		trashcan_emptier = TrashcanEmptyingBehavior("TrashcanEmptyingBehavior", self.interrupt_var_, srv.MOVE_BASE_SERVICE_STR)

		position = self.detected_trash_.detections[0].pose.pose.position
		room_center = self.room_information_in_meter_[room_id].room_center # todo (rmb-ma). use the exact trolley position

		trashcan_emptier.setParameters(trashcan_position=position, trolley_position=room_center)

		trashcan_emptier.executeBehavior()

	# Remove the dirt detected in self.detected_dirt_
	def dirtRoutine(self, room_id):
		if self.detected_dirt_ is None:
			assert False

		self.found_dirtspots_ += 1
		dirt_remover = DirtRemovingBehavior("DirtRemovingBehavior", self.interrupt_var_,
											move_base_service_str=srv.MOVE_BASE_SERVICE_STR,
											map_accessibility_service_str=srv.MAP_ACCESSIBILITY_SERVICE_STR)

		position = self.detected_dirt_.detections[0].pose.pose.position
		dirt_remover.setParameters(dirt_position=position)

		dirt_remover.executeBehavior()

	def callEmptyService(self, service):
		rospy.wait_for_service(service)
		try:
			rospy.ServiceProxy(service, Empty)()
			self.printMsg('Called ' + service)
		except rospy.ServiceException, e:
			self.printMsg("Service call failed: %s" % e)

	def stopDetectionsAndUnregister(self):
		Thread(target=self.callEmptyService, args=(srv.STOP_DIRT_DETECTOR_SERVICE_STR,)).start()
		Thread(target=self.callEmptyService, args=(srv.STOP_TRASH_DETECTOR_SERVICE_STR,)).start()
		if self.dirt_topic_subscriber_ is not None:
			self.dirt_topic_subscriber_.unregister()
		if self.trash_topic_subscriber_ is not None:
			self.trash_topic_subscriber_.unregister()

	def dirtDetectionCallback(self, detections):
		self.printMsg("DIRT DETECTED!!")

		# 1. Stop the dirt and the trash detections
		self.stopDetectionsAndUnregister()

		# 2. Stop the path follower
		self.local_mutex_.acquire()
		self.detected_dirt_ = detections
		self.local_mutex_.release()

		position = self.detected_dirt_.detections[0].pose.pose.position
		print("ON POSITION ({}, {})".format(position.x, position.y))

	def trashDetectionCallback(self, detections):
		self.printMsg("Trash DETECTED!!")

		# 1. Stop the dirt and the trash detections
		self.stopDetectionsAndUnregister()

		# 2. Stop the path follower
		self.local_mutex_.acquire()
		self.detected_trash_ = detections
		self.local_mutex_.release()

		position = self.detected_trash_.detections[0].pose.pose.position
		print("ON POSITION ({}, {})".format(position.x, position.y))

	def computeCoveragePath(self, room_id):
		self.printMsg('Starting computing coverage path of room ID {}'.format(room_id))

		# todo (rmb-ma): why room_explorer is an object attribute?
		self.room_explorer_ = room_exploration_behavior.RoomExplorationBehavior("RoomExplorationBehavior",
																				self.interrupt_var_,
																				self.room_exploration_service_str_)

		room_center = self.room_information_in_meter_[room_id].room_center
		room_map_data = self.database_handler_.database_.getRoomById(room_id).room_map_data_

		self.room_explorer_.setParameters(
			input_map=room_map_data,
			map_resolution=self.database_handler_.database_.global_map_data_.map_resolution_,
			map_origin=self.database_handler_.database_.global_map_data_.map_origin_,
			robot_radius=self.robot_radius_,
			coverage_radius=self.coverage_radius_,
			field_of_view=self.field_of_view_,  # this field of view represents the off-center iMop floor wiping device
			field_of_view_origin=self.field_of_view_origin_,
			starting_position=Pose2D(x=room_center.x, y=room_center.y, theta=0.),
			# todo: determine current robot position
			planning_mode=2
		)
		self.room_explorer_.executeBehavior()
		self.printMsg('Coverage path of room ID {} computed.'.format(room_id))

	def checkoutRoom(self, room_id):
		self.printMsg("checkout dry cleaned room: " + str(room_id))

		cleaning_tasks = self.database_handler_.database_.getRoomById(room_id).open_cleaning_tasks_

		# Many opened tasks (trash + dirt ?) TRASH_TASK = -1 || DRY_TASK = 0

		self.database_handler_.checkoutCompletedRoom(
			self.database_handler_.database_.getRoomById(room_id),
			assignment_type=0)

		# Adding log entry for dry cleaning (but two  )
		self.database_handler_.addLogEntry(
			room_id=room_id,
			status=1,  # 1=Completed
			cleaning_task=0,  # 1=wet only
			found_dirtspots=self.found_dirtspots_,
			found_trashcans=self.found_trashcans_,
			cleaned_surface_area=0,
			room_issues=[],
			used_water_amount=0,
			battery_usage=0
		)

	def executeCustomBehaviorInRoomId(self, room_id):

		self.printMsg('Starting Dry Cleaning of room ID {}'.format(room_id))

		room_center = self.room_information_in_meter_[room_id].room_center

		self.move_base_handler_.setParameters(
			goal_position=room_center,
			goal_orientation=Quaternion(x=0., y=0., z=0., w=1.),
			header_frame_id='base_link'
		)
		thread_move_to_the_room = Thread(target=self.move_base_handler_.executeBehavior)
		thread_move_to_the_room.start()

		self.computeCoveragePath(room_id=room_id)

		path = self.room_explorer_.exploration_result_.coverage_path_pose_stamped

		if self.handleInterrupt() >= 1:
			return

		self.path_follower_ = move_base_path_behavior.MoveBasePathBehavior("MoveBasePathBehavior_PathFollowing",
																			self.interrupt_var_,
																			self.move_base_path_service_str_)

		#with open('/home/rmb/Desktop/rmb-ma_notes/path_visualizer/path.txt', 'w') as f:
		#	f.write(str(path))

		thread_move_to_the_room.join() # don't start the detections before
		while len(path) > 0:
			self.printMsg("Length of computed path {}".format(len(path)))

			cleaning_tasks = self.database_handler_.database_.getRoomById(room_id).open_cleaning_tasks_

			(self.detected_trash_, self.detected_dirt_) = (None, None)

			if True:  # DryCleaningBehavior.containsTrashcanTask(cleaning_tasks):
				Thread(target=self.callEmptyService, args=(srv.START_TRASH_DETECTOR_SERVICE_STR,)).start()
				self.trash_topic_subscriber_ = rospy.Subscriber('trash_detector_topic', DetectionArray, self.trashDetectionCallback)

			if True:  # DryCleaningBehavior.containsDirtTask(cleaning_tasks):
				Thread(target=self.callEmptyService, args=(srv.START_DIRT_DETECTOR_SERVICE_STR,)).start()
				self.dirt_topic_subscriber_ = rospy.Subscriber('dirt_detector_topic', DetectionArray, self.dirtDetectionCallback)

			room_map_data = self.database_handler_.database_.getRoomById(room_id).room_map_data_
			self.path_follower_.setParameters(
				target_poses=path,
				area_map=room_map_data,
				path_tolerance=0.2,
				goal_position_tolerance=0.5,
				goal_angle_tolerance=1.57
			)

			self.path_follower_.setInterruptVar(self.interrupt_var_)
			explorer_thread = Thread(target=self.path_follower_.executeBehavior)
			explorer_thread.start()

			while not self.path_follower_.is_finished:
				self.local_mutex_.acquire()
				if self.detected_dirt_ is not None or self.detected_trash_ is not None:
					self.path_follower_.interruptExecution()
				self.local_mutex_.release()
				rospy.sleep(2)

			explorer_thread.join()

			if self.handleInterrupt() >= 1:
				return

			# todo (rmb-ma) WARNING /!\ If both detections at the same time, the trashcan detection is ignored
			if self.detected_dirt_:
				self.dirtRoutine(room_id=room_id)
			elif self.detected_trash_:
				self.trashcanRoutine(room_id=room_id)

			# start again on the current position
			self.printMsg("Result is {}".format(self.path_follower_.move_base_path_result_))
			last_visited_index = self.path_follower_.move_base_path_result_.last_visited_index
			self.printMsg('Move stopped at position {}'.format(last_visited_index))
			path = path[last_visited_index:]

		# Checkout the completed room
		self.checkoutRoom(room_id=room_id)

	# Implemented Behavior
	def executeCustomBehavior(self):
		self.move_base_handler_ = move_base_behavior.MoveBaseBehavior("MoveBaseBehavior", self.interrupt_var_,
																		srv.MOVE_BASE_SERVICE_STR)
		self.tool_changer_ = tool_changing_behavior.ToolChangingBehavior("ToolChangingBehavior", self.interrupt_var_)
		self.trolley_mover_ = trolley_movement_behavior.TrolleyMovementBehavior("TrolleyMovingBehavior",
																				self.interrupt_var_)
		# Tool change according to cleaning task
		self.tool_changer_.setParameters(self.database_handler_)
		self.tool_changer_.executeBehavior()

		room_counter = 0
		for checkpoint in self.sequencing_result_.checkpoints:
			# Trolley movement to checkpoint
			self.trolley_mover_.setParameters(self.database_handler_)
			self.trolley_mover_.executeBehavior()

			for room_index in checkpoint.room_indices:
				current_room_id = self.mapping_.get(room_counter)
				self.executeCustomBehaviorInRoomId(room_id=current_room_id)
				room_counter = room_counter + 1