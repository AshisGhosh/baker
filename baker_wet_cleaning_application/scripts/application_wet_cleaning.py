#!/usr/bin/env python

import rospy
import actionlib
import application_container
import map_handling_behavior
import dry_cleaning_behavior
import movement_handling_behavior
import database
import database_handler

from geometry_msgs.msg import Point32

class WetCleaningApplication(application_container.ApplicationContainer):

	# Implement application procedures of inherited classes here.
	def executeCustomBehavior(self):

		self.robot_frame_id_ = 'base_link'
		self.robot_radius_ = 0.2875  #0.325	# todo: read from MIRA
		self.coverage_radius_ = 0.233655  #0.25	# todo: read from MIRA
		
		# todo: read out these parameters
		if rospy.has_param('robot_frame'):
			self.robot_frame_id_ = rospy.get_param("robot_frame")
			self.printMsg("Imported parameter robot_frame = " + str(self.robot_frame_id_))
		if rospy.has_param('robot_radius'):
			self.robot_radius_ = rospy.get_param("robot_radius")
			self.printMsg("Imported parameter robot_radius = " + str(self.robot_radius_))
		if rospy.has_param('coverage_radius'):
			self.coverage_radius_ = rospy.get_param("coverage_radius")
			self.printMsg("Imported parameter robot_radius = " + str(self.coverage_radius_))
		# todo: get field_of_view

		self.field_of_view_ = [Point32(x=0.04035, y=0.136), Point32(x=0.04035, y=-0.364),
							   Point32(x=0.54035, y=-0.364), Point32(x=0.54035, y=0.136)]	# todo: read from MIRA

		
		# Load database, initialize database handler
		# ==========================================

		# Initialize and load database
		try:
			self.printMsg("Loading database from files...")
			self.database_ = database.Database(extracted_file_path="")
			self.database_.loadDatabase()
		except:
			self.printMsg("Fatal: Loading of database failed! Stopping application.")
			exit(1)

		# Initialize database handler
		try:
			self.database_handler_ = database_handler.DatabaseHandler(self.database_)
		except:
			self.printMsg("Fatal: Initialization of database handler failed!")
			exit(1)

		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return


		# Find and sort all due rooms
		# ===========================

		# Find due rooms
		self.printMsg("Collecting due rooms...")
		if (self.database_handler_.isFirstStartToday() == True):
			try:
				self.database_handler_.getAllDueRooms()
			except:
				self.printMsg("Fatal: Collecting of the due rooms failed!")
				exit(1)
		else:
			try:
				self.database_handler_.restoreDueRooms()
			except:
				self.printMsg("Fatal: Restoring of the due rooms failed!")
				exit(1)

		# Sort the due rooms after cleaning method
		self.printMsg("Sorting the found rooms after cleaning method...")
		try:
			rooms_dry_cleaning, rooms_wet_cleaning = self.database_handler_.sortRoomsList(self.database_handler_.due_rooms_)
		except:
			self.printMsg("Fatal: Sorting after the cleaning method failed!")
			exit(1)

		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return

		

		# DRY CLEANING OF DUE ROOMS
		# =========================

		# Plan the dry cleaning process
		self.map_handler_ = map_handling_behavior.MapHandlingBehavior("MapHandlingBehavior", self.application_status_)
		self.map_handler_.setParameters(
			self.robot_radius_,
			self.database_,
			rooms_dry_cleaning
		)
		self.map_handler_.executeBehavior()
		#self.printMsg("self.map_handler_.room_sequencing_data_.checkpoints=" + str(self.map_handler_.room_sequencing_data_.checkpoints))
		
		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return

		# Run Dry Cleaning Behavior
		self.dry_cleaner_ = dry_cleaning_behavior.DryCleaningBehavior("DryCleaningBehavior", self.application_status_)
		self.dry_cleaner_.setParameters(
			self.database_handler_
		)
		self.dry_cleaner_.executeBehavior()
		
		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return



		# WET CLEANING OF DUE ROOMS
		# =========================

		self.map_handler_.setParameters(
			self.robot_radius_,
			self.database_handler_,
			rooms_wet_cleaning
		)
		self.map_handler_.executeBehavior()

		# Run Wet Cleaning Behavior
		# TODO: Rename to wet_cleaner
		self.movement_handler_ = movement_handling_behavior.MovementHandlingBehavior("MovementHandlingBehavior", self.application_status_)
		self.movement_handler_.setParameters(
			self.database_handler_,
			self.map_handler_.segmentation_data_,
			self.database_handler_.getRoomInformationInMeter(self.database_handler_.due_rooms_cleaning_),
			self.map_handler_.room_sequencing_data_,
			self.robot_frame_id_,
			self.robot_radius_,
			self.coverage_radius_,
			self.field_of_view_
		)
		self.movement_handler_.executeBehavior()
		
		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return
		


		# Find and sort all overdue rooms
		# ===========================

		# Find overdue rooms
		self.printMsg("Collecting overdue rooms...")
		try:
			self.database_handler_.getAllOverdueRooms()
		except:
			self.printMsg("Fatal: Collecting of the over rooms failed!")
			exit(1)


		# Sort the overdue rooms after cleaning method
		self.printMsg("Sorting the found rooms after cleaning method...")
		try:
			rooms_dry_cleaning, rooms_wet_cleaning = self.database_handler_.sortRoomsList(self.database_handler_.overdue_rooms_)
		except:
			self.printMsg("Fatal: Sorting after the cleaning method failed!")
			exit(1)
		

		# DRY CLEANING OF OVERDUE ROOMS
		# =============================

		self.map_handler_.setParameters(
			self.robot_radius_,
			self.database_handler_,
			is_overdue=True
		)
		self.map_handler_.executeBehavior()

		# Run Dry Cleaning Behavior
		self.dry_cleaner_ = dry_cleaning_behavior.DryCleaningBehavior("DryCleaningBehavior", self.application_status_)
		self.dry_cleaner_.setParameters(
			self.database_handler_
		)
		self.dry_cleaner_.executeBehavior()
		
		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return
		


		# WET CLEANING BEHAVIOR OF OVERDUE ROOMS
		# ======================================

		self.map_handler_.setParameters(
			self.robot_radius_,
			self.database_handler_,
			is_wet=True,
			is_overdue=True
		)
		self.map_handler_.executeBehavior()

		# Run Wet Cleaning Behavior
		# TODO: Rename to wet_cleaner
		self.movement_handler_ = movement_handling_behavior.MovementHandlingBehavior("MovementHandlingBehavior", self.application_status_)
		self.movement_handler_.setParameters(
			self.database_handler_,
			self.map_handler_.segmentation_data_,
			self.database_handler_.getRoomInformationInMeter(self.database_handler_.due_rooms_cleaning_),
			self.map_handler_.room_sequencing_data_,
			self.robot_frame_id_,
			self.robot_radius_,
			self.coverage_radius_,
			self.field_of_view_
		)
		self.movement_handler_.executeBehavior()
		
		# Interruption opportunity
		if self.handleInterrupt() == 2:
			return

		
		# COMPLETE APPLICATION
		# ====================

		self.printMsg("Cleaning completed. Overwriting database...")
		try:
			self.database_handler_.cleanFinished()
		except:
			self.printMsg("Fatal: Database overwriting failed!")
			exit(1)
		






	# Abstract method that contains the procedure to be done immediately after the application is paused.
	def prePauseProcedure(self):
		print "Application: Application paused."
		# save current data if necessary
		# undo or check whether everything has been undone
		self.returnToRobotStandardState()

	# Abstract method that contains the procedure to be done immediately after the pause has ended
	def postPauseProcedure(self):
		print "Application: Application continued."

	# Abstract method that contains the procedure to be done immediately after the application is cancelled.
	def cancelProcedure(self):
		print "Application: Application cancelled."
		# save current data if necessary
		# undo or check whether everything has been undone
		self.returnToRobotStandardState()

	# Method for returning to the standard pose of the robot
	def returnToRobotStandardState(self):
		# save current data if necessary
		self.database_.saveRoomDatabase()
		self.database_.saveApplicationData()
		# undo or check whether everything has been undone



if __name__ == '__main__':
	try:
		# Initialize node
		rospy.init_node('application_wet_cleaning')
		# Initialize application
		app = WetCleaningApplication("application_wet_cleaning", "interrupt_application_wet_cleaning")
		# Execute application
		app.executeApplication()
	except rospy.ROSInterruptException:
		print "Keyboard Interrupt"
	rospy.signal_shutdown("Finished")
