#!/usr/bin/env python

# For the room and robot data information
import database_classes
# For time calculations
from datetime import datetime, date, time, timedelta
# For Point32
from geometry_msgs.msg import Point32
from geometry_msgs.msg import Pose
# For map receiving, for image receiving
import cv2
from cv_bridge import CvBridge, CvBridgeError
# For support of the JSON format
import json
# For copying, finding and deleting JSON files
from shutil import copyfile
import os
# For room information
from ipa_building_msgs.msg import *

# Database class
class Database():
	# Rooms
	rooms_ = []
	# Global map data
	global_map_data_ = None
	# Robot proprties
	robot_properties_ = None
	# Global settings
	global_settings_ = None
	# File names
	rooms_filename_ = ""
	tmp_rooms_filename_ = ""
	global_settings_filename_ = ""
	robot_properties_filename_ = ""
	global_map_data_filename_ = ""
	global_map_image_filename_ = ""

# =========================================================================================
# Test functions
# =========================================================================================

	# Create a dictionary which contains one room with 2 issues
	def createTestRoomDict(self):
		rooms_dict = {}
		rooms_dict[42] = {
			"room_name": "D3.06",
			"room_id": 42,
			"last_successful_cleaning_date": datetime.now().strftime("%Y-%m-%d_%H:%M"),
			"last_cleanup_successful": "False",
			"room_map": None,
			"room_coords": [0, 0, 0],
			"room_issues": {
				1: {
					"issue_type": 12,
					"issue_images": ["~/resources/D3.06_20030201_1.jpg", "~/resources/D3.06_20030201_2.jpg"],
					"issue_coords": [0, 0, 0],
					"issue_date": datetime.now().strftime("%Y-%m-%d_%H:%M"),
					"issue_id": 1
				},
				2: {
					"issue_type": 4,
					"issue_images": ["~/resources/D3.06_20130302_1.jpg", "~/resources/D3.06_20130302_2.jpg"],
					"issue_coords": [0, 0, 0],
					"issue_date": datetime.now().strftime("%Y-%m-%d_%H:%M"),
					"issue_id": 2
				}
			}
		}
		return rooms_dict

	# Add a test room object to the rooms list
	def createTestRoomObject(self):
		# Create room test issue 1
		issue1 = database_classes.RoomIssue()
		issue1.issue_id_ = 1
		issue1.issue_coords_ = None
		issue1.issue_date_ = datetime.now(),
		issue1.issue_images_ = ["~/testordner/OBild1", "~/testordner/OBild2"]
		issue1.issue_type_ = 21
		# Create room test issue 2
		issue2 = database_classes.RoomIssue()
		issue2.issue_id_ = 2
		issue2.issue_coords_ = None
		issue2.issue_date_ = datetime.now(),
		issue2.issue_images_ = ["~/testordner/OBild3", "~/testordner/OBild4"]
		issue2.issue_type_ = 11
		# Create test room
		test_room = database_classes.RoomItem()
		test_room.room_issues_.append(issue1)
		test_room.room_issues_.append(issue2)
		test_room.room_id_ = 42
		#test_room.last_cleanup_successful_ = False
		#test_room.last_successful_cleaning_date_ = None
		test_room.room_map_ = None
		test_room.room_center_coords_ = None
		test_room.room_name_ = "Kitchen"
		# Add room to the room list
		self.rooms_.append(test_room)

# =========================================================================================
# Private methods
# =========================================================================================

	@staticmethod
	def datetimeToString(datetime_date):
		return datetime_date.strftime("%Y-%m-%d_%H:%M")

	@staticmethod
	def stringToDatetime(string_date):
		return datetime.strptime(string_date, "%Y-%m-%d_%H:%M")

	@staticmethod
	def point32ToArray(point32_point):
		return [point32_point.x, point32_point.y, point32_point.z]

	@staticmethod
	def arrayToPoint32(array_point):
		return Point32(x=array_point[0], y=array_point[1], z=array_point[2])
	
	
	def updateGlobalSettings(self, dict):
		self.global_settings_ = database_classes.GlobalSettings()
		self.global_settings_.shall_auto_complete_ = dict.get("shall_auto_complete")
		self.global_settings_.max_aux_time_ = dict.get("max_aux_time")
		self.global_settings_.assignment_timedelta_ = dict.get("assignment_timedelta")

	def getGlobalSettingsDictFromGlobalSettings(self):
		global_settings_dict = {}
		global_settings_dict["shall_auto_complete"] = self.global_settings_.shall_auto_complete_
		global_settings_dict["max_aux_time"] = self.global_settings_.max_aux_time_
		global_settings_dict["assignment_timedelta"] = self.global_settings_.assignment_timedelta_
		return global_settings_dict

	def updateGlobalMapData(self, dict):
		self.global_map_data_ = database_classes.GlobalMapData()
		# Get an open cv representation of the map or None if there is no map
		map_file_path = str(self.extracted_file_path) + str(self.global_map_image_filename_)
		map_opencv = cv2.imread(map_file_path, 0)
		bridge = CvBridge()
		self.global_map_data_.map_image_ = bridge.cv2_to_imgmsg(map_opencv, encoding = "mono8")
		# Get the map resolution
		self.global_map_data_.map_resolution_ = dict.get("map_resolution")
		# Get the map origin
		map_origin_coords = dict.get("map_origin")
		pose = Pose()
		pose.position.x = map_origin_coords[0]
		pose.position.y = map_origin_coords[1]
		pose.position.z = map_origin_coords[2]
		pose.orientation.w = map_origin_coords[3]
		pose.orientation.x = map_origin_coords[4]
		pose.orientation.y = map_origin_coords[5]
		pose.orientation.z = map_origin_coords[6]
		self.global_map_data_.map_origin_ = pose
		# Get the map header frame id
		self.global_map_data_.map_header_frame_id_ = dict.get("map_header_frame_id")

	def updateRobotProperties(self, dict):
		self.robot_properties_ = database_classes.RobotProperties()
		# Exploration server constants
		self.robot_properties_.exploration_robot_radius_ = dict.get("exploration_robot_radius")
		self.robot_properties_.exploration_coverage_radius_ = dict.get("exploration_coverage_radius")
		e_fov_list = dict.get("exploration_field_of_view")
		exploration_field_of_view = [Point32(x=e_fov_list[0][0], y=e_fov_list[0][1]), Point32(x=e_fov_list[1][0], y=e_fov_list[1][1]), Point32(x=e_fov_list[2][0], y=e_fov_list[2][1]), Point32(x=e_fov_list[3][0], y=e_fov_list[3][1])]
		self.robot_properties_.exploration_field_of_view_ = exploration_field_of_view
		# Move_Base server constants
		self.robot_properties_.exploration_header_frame_id_ = dict.get("exploration_header_frame_id")
		# Path following server constants
		self.robot_properties_.path_follow_path_tolerance_ = dict.get("path_follow_path_tolerance")
		self.robot_properties_.path_follow_goal_position_tolerance_ = dict.get("path_follow_goal_position_tolerance")
		self.robot_properties_.path_follow_goal_angle_tolerance_ = dict.get("path_follow_goal_angle_tolerance")
		# Wall following server constants
		self.robot_properties_.wall_follow_path_tolerance_ = dict.get("wall_follow_path_tolerance")
		self.robot_properties_.wall_follow_goal_position_tolerance_ = dict.get("wall_follow_goal_position_tolerance")
		self.robot_properties_.wall_follow_goal_angle_tolerance_ = dict.get("wall_follow_goal_angle_tolerance")

	# Make rooms_ contain all the rooms stated in the dict parameter
	def updateRoomsList(self, dict):
		self.rooms_ = []
		for room_key in dict:
			room_issues = []
			current_room = database_classes.RoomItem()
			# Get all issues of a room and get all properties of those issues
			issues_dict = dict.get(room_key).get("room_issues")
			for issue_key in issues_dict:
				current_issue = database_classes.RoomIssue()
				# Get the room issue ID
				current_issue.issue_id_ = issues_dict.get(issue_key).get("issue_id")
				# Get the room issue type
				current_issue.issue_type_ = issues_dict.get(issue_key).get("issue_type")
				# Get the room issue images
				current_issue.issue_images_ = issues_dict.get(issue_key).get("issue_images")
				# Get the room issue coordinates
				issue_coords_list = issues_dict.get(issue_key).get("issue_coords")
				current_issue.issue_coords_ = Point32(x=issue_coords_list[0], y=issue_coords_list[1], z=issue_coords_list[2])
				# Get the date the issue was detected
				date_str = datetime.strptime(issues_dict.get(issue_key).get("issue_date"), "%Y-%m-%d_%H:%M")
				current_issue.issue_date_ = date_str
				# Append current room issue to the room_issues list
				room_issues.append(current_issue)
			current_room.room_issues_ = room_issues
			# Get the name of the room
			current_room.room_name_ = dict.get(room_key).get("room_name")
			# Get the ID of the room
			current_room.room_id_ = dict.get(room_key).get("room_id")
			# Get the position ID of the room
			current_room.room_position_id_ = dict.get(room_key).get("room_position_id")
			# Get the floor of the room
			current_room.room_floor_id_ = dict.get(room_key).get("room_floor_id")
			# Get the building ID of the room
			current_room.room_building_id_ = dict.get(room_key).get("room_building_id")
			# Get the territory the room is in
			current_room.room_territory_id_ = dict.get(room_key).get("room_territory_id")
			# Get the map of the room
			current_room.room_map_ = dict.get(room_key).get("room_map")
			# Get an open cv representation of the map or None if there is no map
			if (current_room.room_map_ != None):
				room_map_file_path = str(self.extracted_file_path) + str("resources/maps/") + str(current_room.room_map_)
				map_opencv = cv2.imread(room_map_file_path, 0)
				bridge = CvBridge()
				current_room.room_map_data_ = bridge.cv2_to_imgmsg(map_opencv, encoding = "mono8")
			else:
				current_room.room_map_data = None
			# Get the room information
			pixel_coords = dict.get(room_key).get("room_information_in_pixel")
			current_room.room_information_in_pixel_ = RoomInformation()
			current_room.room_information_in_pixel_.room_center = Point32(x=pixel_coords[0][0], y=pixel_coords[0][1], z=pixel_coords[0][2])
			current_room.room_information_in_pixel_.room_min_max.points.append(Point32(x=pixel_coords[1][0], y=pixel_coords[1][1], z=pixel_coords[1][2]))
			current_room.room_information_in_pixel_.room_min_max.points.append(Point32(x=pixel_coords[2][0], y=pixel_coords[2][1], z=pixel_coords[2][2]))
			meter_coords = dict.get(room_key).get("room_information_in_meter")
			current_room.room_information_in_meter_ = RoomInformation()
			current_room.room_information_in_meter_.room_center = Point32(x=meter_coords[0][0], y=meter_coords[0][1], z=meter_coords[0][2])
			current_room.room_information_in_meter_.room_min_max.points.append(Point32(x=meter_coords[1][0], y=meter_coords[1][1], z=meter_coords[1][2]))
			current_room.room_information_in_meter_.room_min_max.points.append(Point32(x=meter_coords[2][0], y=meter_coords[2][1], z=meter_coords[2][2]))
			# Get the room surface type
			current_room.room_surface_type_ = dict.get(room_key).get("room_surface_type")
			# Get the cleaning method of the room
			current_room.room_cleaning_method_ = dict.get(room_key).get("room_cleaning_method")
			# Get the room surface area
			current_room.room_surface_area_ = dict.get(room_key).get("room_surface_area")
			# Get the room trashcan count
			current_room.room_trashcan_count_ = dict.get(room_key).get("room_trashcan_count")
			# Get the days where the room has to be cleaned in a specified way
			current_room.room_scheduled_days_ = dict.get(room_key).get("room_scheduled_days")
			
			## Get the last successful cleaning date if there is any, otherwise set None
			#date_str = dict.get(room_key).get("last_successful_cleaning_date")
			#if (date_str != None):
			#	current_room.last_successful_cleaning_date_ = datetime.strptime(date_str, "%Y-%m-%d_%H:%M")
			#else:
			#	current_room.last_successful_cleaning_date_ = None
			## Get the last successful trashcan date if there is any, otherwise set None
			#date_str = dict.get(room_key).get("last_successful_trashcan_date")
			#if (date_str != None):
			#	current_room.last_successful_trashcan_date_ = datetime.strptime(date_str, "%Y-%m-%d_%H:%M")
			#else:
			#	current_room.last_successful_trashcan_date_ = None
			
			# Get the list with the datestamps
			string_datestamp_list = dict.get(room_key).get("room_cleaning_datestamps")
			datestamps = []
			for datestamp in string_datestamp_list:
				if (datestamp != None):
					datestamps.append(self.stringToDatetime(datestamp))
				else:
					datestamps.append(None)
			current_room.room_cleaning_datestamps_ = datestamps
			
			# Append current room object to the rooms_ list
			self.rooms_.append(current_room)


	# Get a dictionary representation of rooms_
	def getRoomsDictFromRoomsList(self):
		room_dict = {}
		for current_room in self.rooms_:
			# Check if current_room is a room 
			if (isinstance(current_room, database_classes.RoomItem) == True):
				# Make a dict of the issues of current_room
				issues_dict = {}
				for current_issue in current_room.room_issues_:
					# Check if current_issue is an issue
					if (isinstance(current_issue, database_classes.RoomIssue) == True):
						# Fill in a string representation of the date
						date_str_issue = current_issue.issue_date_.strftime("%Y-%m-%d_%H:%M")
						# Fill in the issue coordinates
						ic_x = current_issue.issue_coords_.x
						ic_y = current_issue.issue_coords_.y
						ic_z = current_issue.issue_coords_.z
						issue_coords_list = [ic_x, ic_y, ic_z]
						# Fill in the dictionary with the data
						issues_dict[str(current_issue.issue_id_)] = {
							"issue_id": current_issue.issue_id_,
							"issue_type": current_issue.issue_type_,
							"issue_images": current_issue.issue_images_,
							"issue_coords": issue_coords_list,
							"issue_date": date_str_issue
						}
					else:
						print "[FATAL]: An element in issues array is not an issue object!"
				
				## Fill in the last successful cleaning date if there is any, otherwise fill in None
				#if (current_room.last_successful_cleaning_date_ != None):
				#	date_str_cleaning = current_room.last_successful_cleaning_date_.strftime("%Y-%m-%d_%H:%M")
				#else:
				#	date_str_cleaning = None
				## Fill in the last successful trashcan date if there is any, otherwise fill in None
				#if (current_room.last_successful_trashcan_date_ != None):
				#	date_str_trashcan = current_room.last_successful_trashcan_date_.strftime("%Y-%m-%d_%H:%M")
				#else:
				#	date_str_trashcan = None
				
				# Fill in the datestamps
				datestamp_list = []
				for datestamp in current_room.room_cleaning_datestamps_:
					if datestamp != None:
						datestamp_list.append(self.datetimeToString(datestamp))
					else:
						datestamp_list.append(None)
				# Fill in the room information
				if ((current_room.room_information_in_meter_ != None) and (current_room.room_information_in_pixel_ != None)):
					px_center_list = self.point32ToArray(current_room.room_information_in_pixel_.room_center)
					px_min_list = self.point32ToArray(current_room.room_information_in_pixel_.room_min_max.points[0])
					px_max_list = self.point32ToArray(current_room.room_information_in_pixel_.room_min_max.points[1])
					room_information_in_pixel_list = [px_center_list, px_min_list, px_max_list]
					meter_center_list = self.point32ToArray(current_room.room_information_in_meter_.room_center)
					meter_min_list = self.point32ToArray(current_room.room_information_in_meter_.room_min_max.points[0])
					meter_max_list = self.point32ToArray(current_room.room_information_in_meter_.room_min_max.points[1])
					room_information_in_meter_list = [meter_center_list, meter_min_list, meter_max_list]
				else:
					room_information_in_pixel_list = [None, None, None]
					room_information_in_meter_list = [None, None, None]
				# Fill the dictionary with the data
				room_dict[str(current_room.room_id_)] = {
					"room_id": current_room.room_id_,
					"room_name": current_room.room_name_,
					"room_position_id": current_room.room_position_id_,
					"room_floor_id": current_room.room_floor_id_,
					"room_building_id": current_room.room_building_id_,
					"room_territory_id": current_room.room_territory_id_,
					#"last_successful_cleaning_date": date_str_cleaning,
					#"last_successful_trashcan_date": date_str_trashcan,
					"room_issues": issues_dict,
					"room_map": current_room.room_map_,
					"room_information_in_pixel": room_information_in_pixel_list,
					"room_information_in_meter": room_information_in_meter_list,
					"room_surface_type": current_room.room_surface_type_,
					"room_cleaning_method": current_room.room_cleaning_method_,
					"room_surface_area": current_room.room_surface_area_,
					"room_trashcan_count": current_room.room_trashcan_count_,
					"room_scheduled_days": current_room.room_scheduled_days_,
					"room_cleaning_datestamps": datestamp_list
				}
			else:
				print "[FATAL]: An element in rooms_ array is not a room object!"
		return room_dict



# =========================================================================================
# Public methods
# =========================================================================================

	# Constructor method
	def __init__(self, extracted_file_path=""):
		self.extracted_file_path = extracted_file_path
		self.rooms_filename_ = self.extracted_file_path + str("resources/json/rooms.json")
		self.tmp_rooms_filename_ = self.extracted_file_path + str("resources/json/tmp_rooms.json")
		self.robot_properties_filename_ = self.extracted_file_path + str("resources/json/robot_properties.json")
		self.global_settings_filename_ = self.extracted_file_path + str("resources/json/global_settings.json")
		self.global_map_data_filename_ = self.extracted_file_path + str("resources/json/global_map_data.json")
		self.global_map_image_filename_ = self.extracted_file_path + str("resources/maps/global_map.png")

	# Discard temporal database --> A current progress will be forgotten
	def discardTemporalDatabase(self):
		if (os.path.isfile(self.tmp_rooms_filename_) == True):
			os.remove(str(self.tmp_rooms_filename_))
		self.loadDatabase()

	# Load database data from files
	def loadDatabase(self):
		# Load the room data
		if (os.path.isfile(self.tmp_rooms_filename_) == True):
			file = open(self.tmp_rooms_filename_, "r").read()
		else:
			file = open(self.rooms_filename_, "r").read()
		rooms_dict = json.loads(file)
		self.updateRoomsList(rooms_dict)
		# Load the robot properties
		file = open(self.robot_properties_filename_, "r").read()
		robot_properties_dict = json.loads(file)
		self.updateRobotProperties(robot_properties_dict)
		# Load the global settings
		file = open(self.global_settings_filename_, "r").read()
		global_settings_dict = json.loads(file)
		self.updateGlobalSettings(global_settings_dict)
		# Load the global map data
		file = open(self.global_map_data_filename_, "r").read()
		global_map_data_dict = json.loads(file)
		self.updateGlobalMapData(global_map_data_dict)



	# Save room database data to files
	def saveRoomDatabase(self, temporal=True):
		# Save the room data
		rooms_dict = self.getRoomsDictFromRoomsList()
		rooms_text = json.dumps(rooms_dict, indent=4, sort_keys=True)
		if (temporal == True):
			file = open(self.tmp_rooms_filename_, "w")
		else:
			file = open(self.rooms_filename_, "w")
		file.write(rooms_text)
		if ((temporal == False) and (os.path.isfile(self.tmp_rooms_filename_) == True)):
			os.remove(str(self.tmp_rooms_filename_))



	# Retreive a room by providing a room_id
	def getRoom(self, room_id):
		result = None
		for i in range(len(self.rooms_)):
			if (self.rooms_[i].room_id_ == room_id):
				result = self.rooms_[i]
		return result



"""

# =========================================================================================
# Test routine
# =========================================================================================

# Initialize and load data from the files
db = Database()
db.loadDatabase()
#db.createTestRoomObject()

# Play around with the containing data
print db.getRoom(21).room_issues_[0].issue_id_
print db.getRoom(21).room_name_
print db.getRoom(21).room_information_in_pixel_
print db.getRoom(21).room_information_in_meter_
print db.robot_properties_.exploration_coverage_radius_
print db.getRoom(21).room_map_
print db.getRoom(42).room_map_
print db.global_settings_.shall_auto_complete_
print db.getRoom(21).room_trashcan_count_

# Discard Changes
db.discardTemporalDatabase()

# Save database
db.saveDatabase(temporal=False)

"""