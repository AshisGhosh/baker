#!/usr/bin/env python

from threading import Lock, Thread
import time
import rospy
import behavior_container
import database
import tool_changing_behavior
import trolley_movement_behavior
import room_exploration_behavior
import move_base_path_behavior
import services_params as srv
from geometry_msgs.msg import Pose2D
from cob_object_detection_msgs.msg import DetectionArray
from std_srvs.srv import Empty, EmptyResponse

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

	def __init__(self, behavior_name, interrupt_var):
		super(DryCleaningBehavior, self).__init__(behavior_name, interrupt_var)
		self.path_follower_ = None
		self.detected_dirt_ = None
		self.detected_trash_= None
		self.local_mutex_ = Lock()

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

	# Searching for trashcans
	def trashcanRoutine(self, room_counter):
		# ==========================================
		# insert trashcan handling here
		# ==========================================
		self.database_handler_.checkoutCompletedRoom(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)), -1)

		# Adding log entry for wet cleaning
		self.database_handler_.addLogEntry(
			self.mapping_.get(room_counter), # room id
			1, # status (1=Completed)
			-1, # cleaning task (-1=trashcan only)
			0, # (found dirtspots)
			0, # trashcan count
			0, # surface area
			[], # room issues
			0, # water amount
			0 # battery usage
		)

	# Searching for dirt
	def dirtRoutine(self, room_counter):
		# ==========================================
		# insert dirt removing here
		# ==========================================
		self.database_handler_.checkoutCompletedRoom(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)), 0)


	def callEmptyService(self, service):
		rospy.wait_for_service(service)
		try:
			rospy.ServiceProxy(service, Empty)()
		except rospy.ServiceException, e:
			self.printMsg("Service call failed: %s" % e)

	def dirtDetectionCallback(self, detections):
		self.printMsg("DIRT DETECTED!!")
		# 1. Stop the dirt and the trash detections
		#self.callEmptyService(srv.STOP_DIRT_DETECTOR_SERVICE_STR)
		#self.callEmptyService(srv.STOP_TRASH_DETECTOR_SERVICE_STR)

		# 2. Stop the path follower
		#self.local_mutex_.acquire()
		# todo (rmb-ma) ???
		print("mutex acquired mutex acquired mutex acquired mutex acquired mutex acquired mutex acquired mutex acquired mutex acquired")
		self.detected_dirt_ = "detections[0]"
		#self.local_mutex_.release()


	# Driving through room
	def exploreRoom(self, room_counter):
		# todo (rmb-ma): see if it should be removed
		# ==========================================
		# insert room exploration here
		# ==========================================
		
		# Adding log entry for wet cleaning
		self.database_handler_.addLogEntry(
			self.mapping_.get(room_counter), # room id
			1, # status (1=Completed)
			0, # cleaning task (0=dry only)
			0, # (found dirtspots)
			0, # trashcan count
			0, # surface area
			[], # room issues
			0, # water amount
			0 # battery usage
		)

	def computeCoveragePath(self, room_counter, current_room_index):
		self.printMsg('Starting computing coverage path of room ID'.format(str(self.mapping_.get(room_counter))))

		# todo (rmb-ma): why room_explorer is an object attribute?
		self.room_explorer_ = room_exploration_behavior.RoomExplorationBehavior("RoomExplorationBehavior",
																				self.interrupt_var_,
																				self.room_exploration_service_str_)
		room_center = self.room_information_in_meter_[current_room_index].room_center
		room_map_data = self.database_handler_.database_.getRoom(self.mapping_.get(current_room_index)).room_map_data_

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
		self.printMsg('Coverage path of room ID {} computed.'.format(str(self.mapping_.get(room_counter))))


	def executeCustomBehaviorInRoomCounter(self, room_counter, current_room_index):
		self.printMsg('Starting Dry Cleaning of room ID {}'.format( str(self.mapping_.get(room_counter))))

		self.computeCoveragePath(room_counter=room_counter, current_room_index=current_room_index)

		path = self.room_explorer_.exploration_result_.coverage_path_pose_stamped
		if len(path) == 0:
			return

		# todo (rmb-ma)
		cleaning_tasks = self.database_handler_.database_.getRoom(
			self.mapping_.get(room_counter)).open_cleaning_tasks_

		if DryCleaningBehavior.containsTrashcanTask(cleaning_tasks):
			pass

		if True:#drycleaningbehavior.containsDirtTask(cleaning_tasks):
			self.callEmptyService(srv.START_DIRT_DETECTOR_SERVICE_STR)

			self.printMsg('Subscribing to dirt_detector_topic')
			rospy.Subscriber('dirt_detector_topic', DetectionArray, self.dirtDetectionCallback)

		self.path_follower_ = move_base_path_behavior.MoveBasePathBehavior("MoveBasePathBehavior_PathFollowing",
																		   self.interrupt_var_,
																		   self.move_base_path_service_str_)

		room_map_data = self.database_handler_.database_.getRoom(self.mapping_.get(current_room_index)).room_map_data_
		self.path_follower_.setParameters(
			target_poses=path,
			area_map=room_map_data,
			path_tolerance=0.2,
			goal_position_tolerance=0.5,
			goal_angle_tolerance=1.57
		)

		thread = Thread(target=self.path_follower_.executeBehavior)
		thread.start()

		while self.path_follower_.is_running:
			print(str(self.detected_dirt_) + ' ' + str(self.detected_trash_))
			if self.detected_dirt_ is not None or self.detected_trash_ is not None:
				print("interrupt execution interrupt execution interrupt execution interrupt execution interrupt execution")
				self.path_follower_.interruptExecution()
			rospy.sleep(self.sleep_time_)
		print("self.path_follower is no more running")
		thread.join()


		# exploring_thread = threading.Thread(target = self.exploreRoom(room_counter))
		# exploring_thread.start()
		# if ((0 in cleaning_tasks) == True):
		# 	dirt_thread = threading.Thread(target = self.dirtRoutine(room_counter))
		# 	dirt_thread.start()
		# if ((-1 in cleaning_tasks) == True):
		# 	trashcan_thread = threading.Thread(target = self.trashcanRoutine(room_counter))
		# 	trashcan_thread.start()
		# exploring_thread.join()

		#  a. start detection services for dirt and trash bins and exploration (MoveBasePath)

		# c. loop and test whether dirt or trash bins have been detected (from dirt detection, trash bin detection buffer variable self.dirt_detections_ , self.trash_bin_detections_ -> see 4.b.)
		# do not forget the mutex

		#    i. if (new) detection found -> stop all detection services, abort exploration action, receive currently active waypoint of path
		#    ii. start new behavior for dirt removal or trash bin clearing
		#    iii. move to last waypoint before interruption
		#    iv. start all services for detection and start exploration with reduced path beginning at stored last waypoint

		# Checkout the completed room
		self.printMsg("ID of dry cleaned room: " + str(self.mapping_.get(room_counter)))
		self.printMsg(
			str(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)).open_cleaning_tasks_))



	# Implemented Behavior
	def executeCustomBehavior(self):

		self.tool_changer_ = tool_changing_behavior.ToolChangingBehavior("ToolChangingBehavior", self.interrupt_var_)
		self.trolley_mover_ = trolley_movement_behavior.TrolleyMovementBehavior("TrolleyMovingBehavior",
																				self.interrupt_var_)

		# b. dirt/trash bin detections are received by topic (see 1.b: topic message type: cob_object_detection_msgs/DetectionArray.msg)
		# a call back function a store in buffer, use mutex for safe reading/writing
		# mutex in Python: https://stackoverflow.com/questions/3310049/proper-use-of-mutexes-in-python
		# buffers: self.dirt_detections_ , self.trash_bin_detections_

		# Tool change according to cleaning task
		self.tool_changer_.setParameters(self.database_handler_)
		self.tool_changer_.executeBehavior()

		room_counter = 0

		for checkpoint in self.sequencing_result_.checkpoints:

			# Trolley movement to checkpoint
			self.trolley_mover_.setParameters(self.database_handler_)
			self.trolley_mover_.executeBehavior()

			for room_index in checkpoint.room_indices:

				self.executeCustomBehaviorInRoomCounter(room_counter=room_counter, current_room_index=room_index)

				# plan for room exploration path
				# --> path with waypoints


				room_counter = room_counter + 1
				
