#!/usr/bin/env python

import database
import database_classes
import datetime
from datetime import date


def getTodaysWeekType():
	weekNumber = date.today().isocalendar()[1]
	return weekNumber % 2

def getTodaysWeekDay():
	return date.today().weekday() 


class DatabaseHandler():
	database_ = None
	# The assignment which is due today
	due_assignment_ = None
	# Overdue assignments
	overdue_assignments_ = []
	# Contains all due cleaning rooms from the due assignments and removes them right after they were cleaned
	due_rooms_cleaning_ = []
	# Contains all overdue cleaning rooms and removed them right after they were cleaned
	overdue_rooms_cleaning_ = []
	# Contains all due trashcan rooms from the due assignments and removes them right after they were cleaned
	due_rooms_trashcan_ = []
	# Contains all overdue trashcan rooms and removed them right after they were cleaned
	overdue_rooms_trashcan_ = []

	def __init__(self, database):
		self.database_ = database

	# Check via date if an assignment is due
	def assignmentDateIsDue(datetime_stamp):
		a_timedelta = datetime.timedelta(days=self.database_.global_settings_.assignment_timedelta_)
		return ((datetime_stamp != None) and (datetime_stamp - date.today > a_timedelta))

	# Check via date if a room must be cleaned
	def roomeDateIsDue(datetime_stamp, delta_time):
		r_timedelta = datetime.timedelta(days=delta_time)
		return ((datetime_stamp != None) and (datetime_stamp - date.today > r_timedelta))

	# Method for extracting all due rooms from the due assignment
	def getAllDueAssignmentsAndRooms(self):

		# Get the due assignment
		for assignment in self.database_.assignments_:
			if ((assignment.assignment_week_type_ == getTodaysWeekType()) 
			and (assignment.assignment_week_day_ == getTodaysWeekDay())):
				self.due_assignment_ = assignment
				break

		# Get all rooms unfinished from the due assignment and put them in the respective room array
		for room in self.due_assignment_.scheduled_rooms_cleaning_data_:
			self.due_rooms_cleaning_.append(room)
		for room in self.due_assignment_.scheduled_rooms_trashcan_data_:
			self.due_rooms_trashcan_.append(room)

		# If wanted: Get all overdue assignments in correct order
		# But: Assignments with date "None" shall not be added! 
		# They are new and therefore they could not have been done!
		if (self.database_.global_settings_.do_auto_complete_ == True):
			it_assignment = assignment.prev_assignment_
			while (it_assignment != assignment):
			# Find those assignments whose time stamp is further than 14 days in the past
				if (self.assignmentDateIsDue(it_assignment.last_successful_clean_date_) == True):
					self.overdue_assignments_.append(assignment)
				it_assignment = it_assignment.prev_assignment_
			# Get the rooms which should be contained in the overdue array
			# This is the case, if they are not already in due or overdue array and if the date requires it
			for i in range(len(self.overdue_assignments_)):
				it_assignment = self.overdue_assignments_[i]
				for room in assignment.scheduled_rooms_cleaning_data_:
					if (not(room in self.overdue_rooms_cleaning_) and (DATE) and not(room in self.due_rooms_cleaning_)):
						self.overdue_rooms_cleaning_.append(room)
				for room in assignment.scheduled_rooms_trashcan_data_:
					if (not(room in self.overdue_rooms_trashcan_) and (DATE) and not(room in self.due_rooms_trashcan_)):
					self.overdue_rooms_trashcan_.append(room)


	# Method for setting a room as completed
	def checkoutCompletedRoom(self, room, is_overdue):
		room.last_cleanup_successful_ = True
		room.last_successful_clean_date_ = datetime.datetime.now()
		if (is_overdue == True):
			for it_room in self.overdue_rooms_:
				if (it_room.room_id_ == room.room_id_):
					due_rooms_.remove(it_room)
		else:
			for it_room in self.due_rooms_:
				if (it_room.room_id_ == room.room_id_):
					due_rooms_.remove(it_room)
		# Save all changes to the database
		database_.saveDatabase()

	# Method for setting an overdue assignment as completed if it is complete
	def checkoutAssignment(self, assignment):
		pass

	# Method for creating a map representation of the rooms to be cleaned
	def getRoomsMap(self, want_overdue):
		pass
