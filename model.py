# vim: set ts=4 sw=4 :

#
# Simulation code written by Spencer Tipping
# Licensed under the LGPL, latest version.
#

from random import Random
from sys import stderr
from sys import stdout

#
# Generic simulation code
#

def main ():

	#
	# These are keys used to index connections between nodes.
	#

	class directions:
		north = "n"
		south = "s"
		east = "e"
		west = "w"

	def opposite (s):
		if s == directions.north: return directions.south
		if s == directions.south: return directions.north
		if s == directions.east:  return directions.west
		if s == directions.west:  return directions.east
		return None

	def ordinal (s):
		#
		# Right and down are positive; other directions
		# are negative.
		#

		if s == directions.north or s == directions.west: return -1
		if s == directions.east or s == directions.south: return 1
		return None

	class debugging:
		very_verbose = 5
		quite_verbose = 4
		moderately_verbose = 3
		not_looped = 2
		status = 1
		output = 0
		error = -1
		
		tracing = False
		current_debug = very_verbose

	def debug (level, message_function):
		#
		# I'm using a message function for optimization purposes. If we don't end up
		# using this level of debugging, then there's no reason to compute the string
		# required.
		#

		if level <= debugging.current_debug:
			if level <= debugging.error:
				stderr.write (message_function ())
			else:
				stdout.write (message_function ())

	def shuffle (l):
		r = Random ()
		new_list = [[r.randint (0, len (l)), x] for x in l]
		new_list.sort ()
		return [y[1] for y in new_list]

	class node:
		#
		# Note that these row and file are mainly for reference
		# purposes so that we can have each node print out its
		# contents in a meaningful way.
		#

		#
		# Arranged like this:
		#
		# SSSS A SSS A SSSS
		#      A     A
		# SSSS A SSS A SSSS
		#      ...
		# where vertical is row and horizontal is file.
		#

		def __init__ (self, occupancy_delay_function, row, file, nearest_luggage_bin):
			self.delay = occupancy_delay_function
			self.current_occupants = []
			self.row = row
			self.file = file
			self.nearest_luggage_bin = nearest_luggage_bin
			self.connectors = {directions.north: None, directions.south: None, directions.east: None, directions.west: None}

		def __str__ (self):
			if self.nearest_luggage_bin:
				return " B(%3d, %3d)B " % (self.row, self.file)
			else:
				return "  (%3d, %3d)  " % (self.row, self.file)

		def current_delay (self):
			#
			# For delaying purposes, each bag counts as a fraction of a separate person. This is
			# applicable to airplanes because the aisles are very narrow and a person carrying a
			# suitcase would be difficult to pass.
			#

			return self.delay (sum ([1 + p.number_of_bags_factor () for p in self.current_occupants]))
			
		def available (self):
			return self.current_delay () >= 0 and sum ([1 + p.number_of_bags_factor () for p in self.current_occupants]) < 4

		def enter (self, someone):
			self.current_occupants += [someone]
			someone.location = self
			someone.delays_so_far += self.current_delay ()
			return self

		def leave (self, someone):
			if someone in self.current_occupants:
				self.current_occupants.remove (someone)

		def connect (self, direction, destination):
			#
			# Connects this to another node (and vice versa) and returns the destination.
			#

			self.connectors [direction] = destination
			destination.connectors [opposite(direction)] = self
			return destination

		def shoot_off (self, direction):
			n = self

			while n.connectors [direction]:
				n = n.connectors [direction]

			return n

		def travel (self, direction, distance):
			n = self

			for i in range (distance):
				n = n.connectors [direction]

			return n

		def nearest_aisle (self):
			#
			# Returns a 2-tuple with (distance, aisle_cell).
			#

			if self.connectors [directions.north] or self.connectors [directions.south]:
				return (0, self)
			else:
				west_offshoot = self
				west_counter = 0
				east_offshoot = self
				east_counter = 0

				while west_offshoot.connectors [directions.west] and not \
						(west_offshoot.connectors [directions.north] or west_offshoot.connectors [directions.south]):
					west_offshoot = west_offshoot.connectors [directions.west]
					west_counter += 1

				while east_offshoot.connectors [directions.east] and not \
						(east_offshoot.connectors [directions.north] or east_offshoot.connectors [directions.south]):
					east_offshoot = east_offshoot.connectors [directions.east]
					east_counter += 1

				if not west_offshoot.connectors [directions.west]:
					return (east_counter, east_offshoot)

				if not east_offshoot.connectors [directions.east]:
					return (west_counter, west_offshoot)

				if east_counter < west_counter:
					return (east_counter, east_offshoot)
				else:
					return (west_counter, west_offshoot)

		def trail (self, direction):
			n = self
			t = [n]

			while n.connectors [direction]:
				n = n.connectors [direction]
				t += [n]

			return t

		def compact_representation (self):
			if self.connectors [directions.north] or self.connectors [directions.south]:
				if len (self.current_occupants) > 0:
					return "  |%1dD%03d|  " % (len (self.current_occupants), int (self.current_delay ()))
				else:
					return "  |     |  "
			else:
				if len (self.current_occupants) > 0:
					return " %1dD%03d" % (len (self.current_occupants), int (self.current_delay ()))
				else:
					return " -----"

	class boarder:
		pre_boarding = None
		find_aisle = 0
		find_row = 1
		find_seat = 2

		#
		# Note: The delays_so_far attribute marks how long the boarder has waited to get to his
		# seat, including transportation time! Really, this is a "boarder clock" -- it would
		# correspond exactly to his wristwatch, except that time zero is when the first person
		# steps onto the plane.
		#
		# I'm using self.location to determine whether or not the boarder is on the plane.
		# If they are not, then the location is None, whereas if they are, it will be set
		# to someplace where they can find their way to their seats.
		#
		
		def __init__ (self, location, target, number_of_bags, aisles_on_plane, move_or_wait_decider_function, \
				number_of_bags_delay_per_move_function, number_of_bags_factor_function):
			self.target = target
			self.number_of_bags = number_of_bags
			self.number_of_bags_delay = number_of_bags_delay_per_move_function
			self.number_of_bags_factor_function = number_of_bags_factor_function
			self.delays_so_far = 0
			self.aisles_on_plane = aisles_on_plane
			self.location = boarder.pre_boarding
			self.seek_phase = boarder.find_aisle
			self.move_or_wait_decider = move_or_wait_decider_function
			self.closest_aisle = None
			self.finished = False
			self.sequence_identifier = 0
			self.irritability = 0

			#
			# Create a back-reference to the passenger.
			#

			target.passenger = self
		
		def __str__ (self):
			return "#%4d: %s --> %s; delay %4d; carrying %2d bags" % \
				(self.sequence_identifier, str (self.location), str (self.target), self.delays_so_far, self.number_of_bags)

		def number_of_bags_factor (self):
			return self.number_of_bags_factor_function (self.number_of_bags)

		def move_if_possible (self):
			self.delays_so_far += 1 + self.number_of_bags_delay (self.number_of_bags)

			if not self.finished:
				if self.location.connectors [self.next_direction]:
					if self.move_or_wait_decider (self.next_direction, \
							self.location.connectors [self.next_direction].current_delay () - self.irritability / 100) and \
							self.location.connectors [self.next_direction].available ():
						self.irritability = 0
						self.location.leave (self)
						self.location.connectors [self.next_direction].enter (self)
					else:
						#
						# A strange model: If the irritability is high enough, it will override the person's judgment
						# so that the person will move into a clogged node. This prevents people from waiting forever
						# and resulting in a model deadlock.
						#

						self.irritability += 1

				else:
					debug (debugging.error, lambda: " > %s is trying to go along nonexistent path %s" % (str (self), self.next_direction))

		def step (self, time):
			if self.location and not self.finished:
				if self.seek_phase == boarder.find_aisle:
					#
					# We find the aisle closest to our seat. This is easily accomplished with a couple
					# of for-comprehensions.
					#

					if not self.closest_aisle:
						self.closest_aisle = min ([[abs (a.file - self.target.file), a.file] for a in self.aisles_on_plane]) [1]

					#
					# Now, navigate towards that aisle.
					#

					if self.location.file < self.closest_aisle:
						self.next_direction = directions.east
					elif self.location.file > self.closest_aisle:
						self.next_direction = directions.west
					else:
						self.seek_phase = boarder.find_row

						#
						# We're going to go ahead and fall through to the next if statement.
						#

				if self.seek_phase == boarder.find_row:
					#
					# Now, we embark upon the simple task of locating our row.
					#

					if self.location.row < self.target.row:
						self.next_direction = directions.south
					elif self.location.row > self.target.row:
						self.next_direction = directions.north
					else:
						self.seek_phase = boarder.find_seat

				if self.seek_phase == boarder.find_seat:
					#
					# Finally, we find the seat in question.
					# First, we make sure that we don't have any bags.
					#

					if self.number_of_bags > 0 and self.location.nearest_luggage_bin:
						self.delays_so_far += self.location.nearest_luggage_bin.load_delay (self.number_of_bags)
						self.number_of_bags = 0

					if self.location.file > self.target.file:
						self.next_direction = directions.west
					elif self.location.file < self.target.file:
						self.next_direction = directions.east
					else:
						debug (debugging.quite_verbose, lambda: "Found my seat!")
						self.finished = True

				self.move_if_possible ()

	class luggage_bin:
		def __init__ (self, bag_capacity, load_delay_function):
			self.bag_capacity = bag_capacity
			self.current_load = 0
			self.delay = load_delay_function

		def load_one_bag (self):
			self.current_load += 1
			return self.delay (self.current_load, self.bag_capacity)

		def load_delay (self, additional_load):
			return sum ([self.load_one_bag () for i in range (additional_load)])
			
	class aisle:
		#
		# An aisle is just the collection of nodes that makes up the
		# aisle portion of an aircraft. It does not include any seats.
		# Seats are added by using add_window_row and add_bridge_row.
		#
		
		def __init__ (self, rows, occupancy_delay_function, file, bin_capacity, bin_load_delay_function, bin_row_span):
			last_bin = luggage_bin (bin_capacity, bin_load_delay_function)
			self.head = node (occupancy_delay_function, 0, file, last_bin)
			self.file = file
			self.nodes = self.head,
			self.rows = rows
			p = self.head
			last_bin_row = 1
			
			#
			# The rows will go from 0 to rows - 1, inclusive.
			# I'm using 1..rows because this translates to 1..rows - 1, and we
			# added the zero row above.
			#

			for i in range (1, rows):
				if i > last_bin_row + bin_row_span - 1:
					last_bin = luggage_bin (bin_capacity, bin_load_delay_function)
					last_bin_row = i

				n = node (occupancy_delay_function, i, file, last_bin)
				p.connect (directions.south, n)
				self.nodes += n,
				p = n

			self.tail = n

		def add_window_row (self, row, direction, files, occupancy_delay_function, major_file):
			#
			# Returns the window seat.
			#
			
			base = self.nodes [row]
			
			for i in range (files):
				base = base.connect (direction, node (occupancy_delay_function, row, self.file + (i+1) * ordinal (direction), None))
				base.major_file = major_file

			return base

		def add_bridge_row (self, bridged_aisle, row, direction, files, occupancy_delay_function, major_file):
			#
			# Returns the seat in the bridged aisle to which this aisle connects.
			#

			return self.add_window_row (row, direction, files, occupancy_delay_function, major_file).connect ( \
					direction, bridged_aisle.nodes [row])

	class grid_plane_geometry:
		def __init__ (self, rows, file_count_list, aisle_occupancy_delay_function, seat_occupancy_delay_function, \
				row_select_function, number_of_bags_function, move_or_wait_decider_function, \
				number_of_bags_delay_function, number_of_bags_factor_function, bin_capacity, \
				bin_load_delay_function, bin_row_span):

			#
			# Build the aisles at the appropriate files. The reason I'm subtracting one
			# is because there are three file widths here, and only two aisles:
			#
			#   3   3   4
			#  SSS|SSS|SSSS
			#  SSS|SSS|SSSS
			#
			#    ...
			#

			self.aisles = [aisle (rows + 1, aisle_occupancy_delay_function, sum (file_count_list [0:i+1]) + i, \
					bin_capacity, bin_load_delay_function, bin_row_span) \
					for i in range (len (file_count_list) - 1)]

			self.file_count_list = file_count_list
			self.start_location = self.aisles [0].head
			self.passengers = []
			self.rows = rows + 1

			#
			# Create the bridge for the first row. There won't be passengers here, just some nodes
			# to allow them to cross.
			#

			for aisle_index in range (1, len (self.aisles)):
				self.aisles [aisle_index - 1].add_bridge_row ( \
					self.aisles [aisle_index], 0, directions.east, file_count_list [aisle_index], aisle_occupancy_delay_function, aisle_index)

			for row in range (1, rows + 1):
				#
				# First, connect all of the aisles together east-west.
				#

				self.aisles [0].add_window_row (row, directions.west, file_count_list [0], seat_occupancy_delay_function, 0)

				for aisle_index in range (1, len (self.aisles)):
					self.aisles [aisle_index - 1].add_bridge_row ( \
						self.aisles [aisle_index], row, directions.east, file_count_list [aisle_index], \
							seat_occupancy_delay_function, aisle_index)

				self.aisles [len (self.aisles) - 1].add_window_row (row, directions.east, file_count_list [len (file_count_list) - 1], \
						seat_occupancy_delay_function, len (self.aisles))

				#
				# Next, put a passenger in each seat.
				# However, we're using the filter-lambda combination to eliminate aisle seats
				# from that list (those being ones with north or south connections).
				#

				self.passengers += [boarder (boarder.pre_boarding, x, number_of_bags_function (), \
						self.aisles, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function) \
						for x in filter (lambda cell: not (cell.connectors [directions.north] or cell.connectors [directions.south]), \
							self.row (row))]

			#
			# Now, re-index all of the passengers.
			#

			for i in range (len (self.passengers)):
				self.passengers [i].sequence_identifier = i

		def row (self, index):
			return self.aisles [0].nodes [index].shoot_off (directions.west).trail (directions.east)

		def __str__ (self):
			s = ""
			for i in range (self.rows):
				for cell in self.row (i):
					s += str (cell)
				s += "\n"
			return s

		def compact_representation (self):
			s = ""
			for i in range (self.rows):
				for cell in self.row (i):
					s += cell.compact_representation ()
				s += "\n"
			return s

	class two_floor_plane_geometry:
		upper_floor = "upper"
		lower_floor = "lower"

		def __init__ (self, lower_geometry, upper_geometry, floor_change_time_function):
			self.lower_geometry = lower_geometry
			self.upper_geometry = upper_geometry
			self.floor_change_time_function = floor_change_time_function
			self.passengers = lower_geometry.passengers + upper_geometry.passengers
			self.start_location = lower_geometry.start_location
			self.rows = lower_geometry.rows

			#
			# Change the floors of each geometry.
			#

			for row in range (lower_geometry.rows):
				for cell in lower_geometry.row (row):
					cell.floor = two_floor_plane_geometry.lower_floor

			for row in range (upper_geometry.rows):
				for cell in upper_geometry.row (row):
					cell.floor = two_floor_plane_geometry.upper_floor

		def board (self, passenger):
			if passenger.target.floor == two_floor_plane_geometry.upper_floor:
				self.upper_geometry.start_location.enter (passenger)
			else:
				self.lower_geometry.start_location.enter (passenger)

		def available (self):
			return len (self.upper_geometry.start_location.current_occupants) == 0 and \
				   len (self.lower_geometry.start_location.current_occupants) == 0

		def compact_representation (self):
			return "Upper floor:\n" + self.upper_geometry.compact_representation () + \
				   "\nLower floor:\n" + self.lower_geometry.compact_representation ()

	class combined_plane_geometry:
		def __init__ (self, north_geometry, south_geometry, binding_function = \
				lambda north, south: [north.aisles [x].tail.connect (directions.south, south.aisles [x].head) \
					for x in range (len (north.aisles))]):

			binding_function (north_geometry, south_geometry)
			self.passengers = [p for p in north_geometry.passengers + south_geometry.passengers]
			self.rows = north_geometry.rows + south_geometry.rows
			self.aisles = north_geometry.aisles

			self.north_geometry = north_geometry
			self.south_geometry = south_geometry

			#
			# Add the new sequencing index to the south group of passengers.
			# Also, properly set their aisle knowledge.
			#

			max_in_north = max ([p.sequence_identifier for p in north_geometry.passengers])
			for p in south_geometry.passengers:
				p.sequence_identifier += max_in_north
				p.aisles_on_plane = north_geometry.aisles

			#
			# Also, update the row indices appropriately.
			# To do this, we'll just bump them up by the number of rows in the northern part.
			#

			for row_index in range (south_geometry.rows):
				for n in south_geometry.row (row_index):
					n.row += north_geometry.rows

			binding_function (north_geometry, south_geometry)

		def row (self, index):
			if index >= self.north_geometry.rows:
				return self.north_geometry.row (index)
			else:
				return self.south_geometry.row (index)

		def __str__ (self):
			return str (self.north_geometry) + "\n\n" + str (self.south_geometry)

		def compact_representation (self):
			return self.north_geometry.compact_representation () + "\n\n" + self.south_geometry.compact_representation ()

	class single_entrance_manager:
		def __init__ (self, entrance):
			self.entrance = entrance

		def board (self, person):
			self.entrance.enter (person)

		def available (self):
			return len (self.entrance.current_occupants) == 0

	class multiple_entrance_manager:
		def __init__ (self, entrances, \
				chooser_function = lambda e, p: min ([[len (e.current_occupants), e] for e in entrances]) [1]):

			self.entrances = entrances
			self.chooser_function = None

		def board (self, person):
			chooser_function (self.entrances, person).enter (person)

		def available (self):
			return min ([e.current_occupants for e in self.entrances]) == 0

	class simulation:
		def __init__ (self, plane, boarding_function):
			self.plane = plane
			self.boarding_function = boarding_function

		def run (self, passenger_selector_function = lambda p: True, boarding_delay_function = lambda: 8, time_step = 1):
			time = 0
			iterations = 0

			debug (debugging.status, lambda: "Beginning simulation...")
			debug (debugging.not_looped, lambda: str (self.plane) + "\n")

			currently_unboarded = self.plane.passengers
			currently_unfinished = []

			queue = []

			while len (currently_unfinished) or len (currently_unboarded) > 0 or len (queue) > 0:
				iterations += 1

				if debugging.tracing and iterations % 100 == 0:
					stderr.write (self.plane.compact_representation () + "\n" + str (int (time)) + "\n")

				if len (queue) == 0 and len (currently_unboarded) > 0:
					#
					# The boarding function is used so that we can choose to board people in
					# stages; for example, we may want to board first-class first and then let
					# everyone else file in randomly.
					#

					queue += self.boarding_function (time, currently_unboarded)
					debug (debugging.quite_verbose, lambda: "Enqueued %d person(s)" % len (queue))
					for passenger in queue:
						if passenger in currently_unboarded:
							currently_unboarded.remove (passenger)

				#
				# The plane will decide how to board queued passengers.
				#

				if len (queue) > 0 and self.plane.available ():
					debug (debugging.quite_verbose, lambda: "Plane: Boarding one person")
					passenger = queue.pop (0)

					#
					# Add this passenger to the "unfinished" list and board them onto the plane.
					# Also, set the clock for that person to be synchronized with the "since-the-beginning-
					# of-the-boarding-process" clock, and set the appropriate delay before adding the
					# next person.
					#

					currently_unfinished += [passenger]
					self.plane.board (passenger)
					passenger.delays_so_far = time
					time += boarding_delay_function ()

				else:
					#
					# Just do the standard time increment to keep the simulation moving.
					#

					time += time_step

				not_caught_up = filter (lambda p: p.delays_so_far < time, currently_unfinished)

				while len (not_caught_up) > 0:
					for passenger in not_caught_up:
						passenger.step (time)

						if passenger.finished:
							not_caught_up.remove (passenger)
							currently_unfinished.remove (passenger)
						elif passenger.delays_so_far >= time:
							#
							# I know that it's not entirely natural to make this an elif, but
							# we don't want the person to be removed twice if they finished and caught
							# up with the master timer.
							#

							not_caught_up.remove (passenger)

			return time

#
# Planes
#

	class airbus_320 (single_entrance_manager, grid_plane_geometry):
		name = "airbus-320"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			grid_plane_geometry.__init__ (self, 23, (3, 3), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
					lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
					number_of_bags_factor_function, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	S1 = airbus_320

	class boeing_767_200 (single_entrance_manager, combined_plane_geometry):
		name = "boeing-767-200"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			combined_plane_geometry.__init__ (self, \
					grid_plane_geometry (8, (2, 2, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
							lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
							number_of_bags_factor_function, 8, bin_load_delay_function, 3), \
					grid_plane_geometry (25, (2, 3, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
							lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
							number_of_bags_factor_function, 8, bin_load_delay_function, 3))

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	S2 = boeing_767_200

	class boeing_767_400 (single_entrance_manager, combined_plane_geometry):
		name = "boeing-767-400"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			combined_plane_geometry.__init__ (self, \
					grid_plane_geometry (8, (2, 2, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
							lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
							number_of_bags_factor_function, 8, bin_load_delay_function, 3), \
					grid_plane_geometry (25, (2, 3, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
							lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
							number_of_bags_factor_function, 8, bin_load_delay_function, 3))

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	M1 = boeing_767_400

	class airbus_a300_600 (single_entrance_manager, grid_plane_geometry):
		name = "airbus-a300-600"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			grid_plane_geometry.__init__ (self, 50, (2, 4, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
					lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
					number_of_bags_factor_function, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	M2 = airbus_a300_600

	class boeing_747 (single_entrance_manager, grid_plane_geometry):
		name = "boeing-747"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			grid_plane_geometry.__init__ (self, 40, (3, 4, 3), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
					lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
					number_of_bags_factor_function, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	L1 = boeing_747

	class airbus_380 (single_entrance_manager, two_floor_plane_geometry):
		name = "airbus-380"

		def __init__ (self, aisle_occupancy_delay_function, seat_occupancy_delay_function, number_of_bags_function, \
				bin_load_delay_function, move_or_wait_decider_function, number_of_bags_delay_function, number_of_bags_factor_function):
			two_floor_plane_geometry.__init__ (self, \
					grid_plane_geometry (40, (3, 4, 3), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
						lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
						number_of_bags_factor_function, 4, bin_load_delay_function, 2), \
					grid_plane_geometry (30, (2, 4, 2), aisle_occupancy_delay_function, seat_occupancy_delay_function, \
						lambda row: True, number_of_bags_function, move_or_wait_decider_function, number_of_bags_delay_function, \
						number_of_bags_factor_function, 4, bin_load_delay_function, 2), \
					seat_occupancy_delay_function)

		def board (self, passenger):
			two_floor_plane_geometry.board (self, passenger)

		def available (self):
			return two_floor_plane_geometry.available (self)

	L2 = airbus_380

#
# Test code
#

	#
	# Passenger queues
	#

	def blocks (unboarded_passengers, number_of_blocks):
		#
		# This isn't a queue function; rather, it just breaks the plane
		# into roughly equal blocks (actually, the blocks are adaptively
		# sized to be roughly equal for the number of passengers remaining).
		#

		farthest_back_row = max ([p.target.row for p in unboarded_passengers])

		#
		# Choose even sections.
		#

		zone = range (number_of_blocks)
		for i in range (len (zone)):
			zone [i] = filter (lambda p: p.target.row * number_of_blocks / (farthest_back_row + 1) == i, unboarded_passengers)

		return zone

	def random_loader (time, unboarded_passengers):
		return shuffle (unboarded_passengers)
	random_loader.name = "pre_assigned_random"

	def sequential_loader (time, unboarded_passengers):
		return unboarded_passengers
	sequential_loader.name = "sequential"

	def sequential_block_loader (time, unboarded_passengers):
		b = blocks (shuffle (unboarded_passengers), 5)
		return b[0] + b[1] + b[2] + b[3] + b[4]
	sequential_block_loader.name = "sequential_block"

	def reverse_block_loader (time, unboarded_passengers):
		b = blocks (shuffle (unboarded_passengers), 5)
		return b[4] + b[3] + b[2] + b[1] + b[0]
	reverse_block_loader.name = "reverse_block"

	def reverse_loader (time, unboarded_passengers):
		unboarded_passengers.reverse ()
		return unboarded_passengers
	reverse_loader.name = "reverse_sequential"

	def outside_in_loader (time, unboarded_passengers):
		maximum_distance_to_aisle = max ([p.target.nearest_aisle ()[0] for p in unboarded_passengers])
		return filter (lambda p: p.target.nearest_aisle ()[0] == maximum_distance_to_aisle, shuffle (unboarded_passengers))
	outside_in_loader.name = "outside_in"

	def reverse_pyramid_loader (time, unboarded_passengers):
		maximum_distance_to_aisle = max ([p.target.nearest_aisle ()[0] for p in unboarded_passengers])
		farthest_back_row = max ([p.target.row for p in unboarded_passengers])

		return filter (lambda p: \
				(maximum_distance_to_aisle - p.target.nearest_aisle ()[0]) * (farthest_back_row / 2) < \
				p.target.row, shuffle (unboarded_passengers))
	reverse_pyramid_loader.name = "reverse_pyramid"

	def rotating_block_loader (time, unboarded_passengers):
		b = blocks (shuffle (unboarded_passengers), 5)
		return b[0] + b[4] + b[1] + b[3] + b[2]
	rotating_block_loader.name = "rotating_block"

	#
	# Variations on the queue functions
	#

	def staggered_adapter (previous_method):
		return lambda time, unboarded_passengers: \
				filter (lambda p: p.target.row % 2 == p.target.major_file % 2, previous_method (time, unboarded_passengers)) + \
				filter (lambda p: p.target.row % 2 != p.target.major_file % 2, previous_method (time, unboarded_passengers))
	staggered_adapter.name = "staggered"

	def even_odd_adapter (previous_method):
		return lambda time, unboarded_passengers: \
				filter (lambda p: p.target.row % 2 == 0, previous_method (time, unboarded_passengers)) + \
				filter (lambda p: p.target.row % 2 == 1, previous_method (time, unboarded_passengers))
	even_odd_adapter.name = "even_odd"

	def identity_adapter (previous_method):
		return lambda time, unboarded_passengers: previous_method (time, unboarded_passengers)
	identity_adapter.name = "original"

	#
	# Running routines
	#

	def plane_generator (plane, r, aisle_delay = 4.0, aisle_min_delay = 3.0, seat_delay = 15.0, bin_load_delay = 3.0):
		#
		# Here I'm storing some default parameters for running. These seem to work fairly well.
		#

		return plane (	aisle_occupancy_delay_function	= lambda n: 1 + (n**2 * max ([r.gauss (aisle_delay, aisle_delay / 4.0), aisle_min_delay])), \
						seat_occupancy_delay_function	= lambda n: 2 + n**3 * r.gauss (seat_delay, seat_delay * 4.0 / 15.0), \
						number_of_bags_function			= lambda: r.randint (0, 2), \
						bin_load_delay_function			= lambda t, c: t * r.gauss (bin_load_delay, bin_load_delay / 6.0), \
						move_or_wait_decider_function	= \
						lambda direction, delay: (delay < 10 and (direction == directions.south or direction == directions.north)) or \
												 (delay < 30 and direction != directions.south and directions != directions.north), \
						number_of_bags_factor_function	= lambda n: n * 0.3, \
						number_of_bags_delay_function	= lambda n: n * 0.5)

	def run_single_simulation ():
		r = Random ()

		debugging.current_debug = debugging.output
		debugging.tracing = True

		debug (debugging.status, lambda: "Building aircraft model and passenger list...")
		debug (debugging.output, lambda: "Simulation: boarding took %d units of time." % \
				simulation (plane_generator (S2, r), \
					boarding_function = staggered_adapter (reverse_pyramid_loader)).run ( \
						passenger_selector_function		= lambda passenger: True, \
						boarding_delay_function			= lambda: r.gauss (7.0, 1.0), \
						time_step						= 0.5))

	def run_statistical_batch_simulation (sensitivity_test_levels):
		r = Random ()

		debugging.current_debug = debugging.error
		debugging.tracing = False

		boarding_functions = (reverse_block_loader, rotating_block_loader, random_loader, reverse_pyramid_loader, outside_in_loader)
		planes = (S2, S1, M1, M2, L1, L2)
		#adapters = (identity_adapter, even_odd_adapter, staggered_adapter)
		adapters = [identity_adapter]
		
		adjustable_parameters = (4.0, 15.0, 3.0, 7.0)

		possibilities = [[1.0, 1.0, 1.0, d] for d in sensitivity_test_levels.keys ()] + [[1.0, 1.0, c, 1.0] for c in sensitivity_test_levels.keys ()] + \
						[[1.0, b, 1.0, 1.0] for b in sensitivity_test_levels.keys ()] + [[a, 1.0, 1.0, 1.0] for a in sensitivity_test_levels.keys ()]

		sensitivity_test_levels[1.0] = 'n'

		possibility_description = lambda p: sensitivity_test_levels[p[0]] + sensitivity_test_levels[p[1]] + \
											sensitivity_test_levels[p[2]] + sensitivity_test_levels[p[3]]

		trials_per_configuration = 25
		time_step = 1

		for plane in planes:
			for possibility in possibilities:
				if len (possibilities) > 1:
					current_file = file (plane.name + possibility_description (possibility), 'w')
				else:
					current_file = file (plane.name, 'w')
				
				for a in adapters:
					for b in boarding_functions:
						current_file.write ("%s_%s\t" % (a.name, b.name))
						stderr.write ("%s_%s\n" % (a.name, b.name))
						
				current_file.write ("\n")
				
				for trial in range (trials_per_configuration):
					for a in adapters:
						for b in boarding_functions:
							immediate_result = str (simulation ( \
									plane = plane_generator (plane, r, \
										adjustable_parameters [0] * possibility [0], adjustable_parameters [0] * possibility [0] * 0.75, \
										adjustable_parameters [1] * possibility [1], adjustable_parameters [2] * possibility [2]), \
									boarding_function = a (b)).run ( \
										passenger_selector_function		= lambda passenger: True, \
										boarding_delay_function			= lambda: \
											r.gauss (adjustable_parameters [3] * possibility [3], 1.0 * possibility [3]), \
										time_step						= time_step))

							current_file.write (immediate_result + "\t")
							stderr.write (immediate_result + "\n")

					current_file.write ("\n")
					current_file.flush ()
					stderr.write ("\n")

				current_file.close ()

#	run_single_simulation ()
	run_statistical_batch_simulation ({1.75: 'h', 0.5: 'l'})

main ()
