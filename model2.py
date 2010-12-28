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
		
		tracing = True
		current_debug = very_verbose

	def debug (level, message_function):
		#
		# I'm using a message function for optimization purposes. If we don't end up
		# using this level of debugging, then there's no reason to compute the string
		# required.
		#

		if level <= debugging.current_debug:
			if level >= debugging.error:
				stdout.write (message_function () + "\n")
			else:
				stderr.write (message_function () + "\n")

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

		def __init__ (self, row, file, nearest_luggage_bin):
			self.current_occupant = None
			self.row = row
			self.file = file
			self.nearest_luggage_bin = nearest_luggage_bin
			self.connectors = {directions.north: None, directions.south: None, directions.east: None, directions.west: None}

		def __str__ (self):
			if self.nearest_luggage_bin:
				return " B(%3d, %3d)B " % (self.row, self.file)
			else:
				return "  (%3d, %3d)  " % (self.row, self.file)

		def available (self):
			return self.current_occupant == None

		def enter (self, someone):
			self.current_occupant = someone
			someone.location = self
			return self

		def leave (self, someone):
			self.current_occupant = None
			return self

		def connect (self, direction, destination):
			#
			# Connects this to another node (and vice versa) and returns the destination.
			#

			self.connectors [direction] = destination
			destination.connectors [opposite(direction)] = self
			return destination

		def is_seat (self):
			return not (self.connectors [directions.north] or self.connectors [directions.south])

		def is_aisle (self):
			return self.connectors [directions.north] or self.connectors [directions.south]

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

		def travel_until_empty (self, direction):
			n = self
			count = 0

			#
			# This function stops on borrowed nodes.
			#

			while n.connectors [direction] and n.connectors [direction].current_occupant and \
					n.connectors [direction].current_occupant.location == n.connectors [direction]:
				n = n.connectors [direction]
				count += 1

			return (count, n)

		def nearest_aisle (self):
			#
			# Returns a 2-tuple with (distance, aisle_cell).
			#

			if self.is_aisle ():
				return (0, self)
			else:
				west_offshoot = self
				west_counter = 0
				east_offshoot = self
				east_counter = 0

				while west_offshoot.connectors [directions.west] and not west_offshoot.connectors [directions.west].is_aisle ():
					west_offshoot = west_offshoot.connectors [directions.west]
					west_counter += 1

				while east_offshoot.connectors [directions.east] and not east_offshoot.connectors [directions.east].is_aisle ():
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
			if self.current_occupant:
				if self.current_occupant.location != self:
					#
					# The occupant is borrowing a cell.
					#

					return " -%03d-%01d- " % (self.current_occupant.personal_delay_counter, self.current_occupant.number_of_bags)
				else:
					if self.is_aisle ():
						return " #%03d-%01d# " % (self.current_occupant.personal_delay_counter, self.current_occupant.number_of_bags)
					else:
						return " ++%03d++ " % (self.current_occupant.needed_to_wait)
			else:
				if self.is_aisle ():
					return "    |    "
				else:
					return "    -    "

	class boarder:
		pre_boarding = None

		find_aisle = 0
		find_row = 1
		find_seat = 2

		#
		# I'm using self.location to determine whether or not the boarder is on the plane.
		# If they are not, then the location is None, whereas if they are, it will be set
		# to someplace where they can find their way to their seats.
		#
		
		def __init__ (self, location, target, number_of_bags, aisles_on_plane, SS, AS, SA, AA):
			self.target = target
			self.number_of_bags = number_of_bags
			self.personal_delay_counter = 0
			self.aisles_on_plane = aisles_on_plane
			self.location = boarder.pre_boarding
			self.seek_phase = boarder.find_aisle
			self.closest_aisle = None
			self.SS = SS
			self.SA = SA
			self.AS = AS
			self.AA = AA
			self.sequence_identifier = 0
			self.needed_to_wait = 0
			self.borrowed_cells = []

			#
			# Create a back-reference to the passenger.
			#

			target.passenger = self
		
		def __str__ (self):
			return "#%4d: %s --> %s; delay %4d; carrying %2d bags" % \
				(self.sequence_identifier, str (self.location), str (self.target), self.personal_delay_counter, self.number_of_bags)

		def number_of_bags_factor (self):
			return self.number_of_bags_factor_function (self.number_of_bags)

		def finished (self):
			return self.location == self.target and self.personal_delay_counter == 0

		def step (self):
			if self.personal_delay_counter == 0:
				for cell in self.borrowed_cells:
					if cell.current_occupant == self:
						cell.current_occupant = None
					else:
						debug (debugging.error, lambda: "%s: Inconsistency in cell ownership of %s" % (str (self.location), str (cell)))

				self.borrowed_cells = []

				if self.location != self.target and self.location:
					if self.seek_phase == boarder.find_aisle:
						#
						# We find the aisle closest to our seat.
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
							self.next_direction = None

						if self.next_direction:
							if self.location.connectors [self.next_direction].available ():
								self.personal_delay_counter += self.AA ()
								self.location.leave (self).connectors [self.next_direction].enter (self)
							else:
								self.needed_to_wait += 1

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
							self.next_direction = None
						
						if self.next_direction:
							if self.location.connectors [self.next_direction]:
								if self.location.connectors [self.next_direction].available ():
									self.location.leave (self).connectors [self.next_direction].enter (self)
									self.personal_delay_counter += self.AA ()
								else:
									self.needed_to_wait += 1
									#debug (debugging.very_verbose, lambda: " > Waiting")
							else:
								debug (debugging.error, lambda: " > %s is trying to go along nonexistent path %s" % (str (self), self.next_direction))

					if self.seek_phase == boarder.find_seat:
						#
						# Finally, we find the seat in question.
						# First, we make sure that we don't have any bags.
						#

						if self.number_of_bags > 0 and self.location.nearest_luggage_bin:
							self.personal_delay_counter += self.location.nearest_luggage_bin.load_delay (self.number_of_bags)
							self.number_of_bags = 0

						if self.location.file > self.target.file:
							self.next_direction = directions.west
						elif self.location.file < self.target.file:
							self.next_direction = directions.east
						else:
							debug (debugging.quite_verbose, lambda: "Found my seat!")
							self.next_direction = None

						if self.next_direction and self.location != self.target and self.location.connectors [self.next_direction]:
							if self.location.connectors [self.next_direction].available ():
								#
								# This is the simplest case. The cell that we want to move into is available.
								#

								if self.location.is_aisle ():
									self.personal_delay_counter += self.AS ()
								else:
									self.personal_delay_counter += self.SS ()
								
								self.borrowed_cells += [self.location]
								self.location.connectors [self.next_direction].enter (self)
							else:
								#
								# We need to figure out how many people we have to cross.
								#

								number_of_people_to_cross = self.location.travel_until_empty (self.next_direction) [0]
								
								if number_of_people_to_cross == 0:
									#
									# The adjacent cell is borrowed, so we must wait for it to clear.
									#

									self.needed_to_wait += 1
								else:
									#
									# If we can borrow a spot in the aisle, then do that.
									# To pull off the borrowing part, we'll be in both places simultaneously. :)
									#

									next_cell = self.location.connectors [self.next_direction]
									
									if self.location.is_aisle ():
										#
										# Try to claim adjacency for the aisle so that we can get more space
										# and avoid shuffling (not explcitly simulated).
										#
										
										south_aisle_cell = self.location.connectors [directions.south]
										if south_aisle_cell and south_aisle_cell.available ():
											#
											# We have more space to work with, so we can save some time.
											#

											mandatory_delay = 0
										else:
											#
											# Simulate some aisle-shuffling that would take extra time.
											#

											mandatory_delay = self.AA () + self.AA ()

										if number_of_people_to_cross == 1:
											#
											# The cell may be borrowed. This is possible because travel_until_empty stops
											# when it hits a borrowed or empty cell.
											#

											if next_cell.connectors [self.next_direction].available ():
												self.borrowed_cells += [self.location]

												if south_aisle_cell and south_aisle_cell.available ():
													self.borrowed_cells += [south_aisle_cell]
													south_aisle_cell.current_occupant = self

												mandatory_delay += max (self.AA (), self.SS ()) + self.AS () + max (self.SS (), self.AS ())
												self.personal_delay_counter += mandatory_delay
												next_cell.current_occupant.personal_delay_counter += mandatory_delay
												next_cell.connectors [self.next_direction].enter (self)
											else:
												self.needed_to_wait += 1

										elif number_of_people_to_cross == 2:
											#
											# If we have to cross two people, then we are going after our target because
											# no seat is farther than three away from the aisle.
											#

											if self.target.available ():
												self.borrowed_cells += [self.location]
												
												if south_aisle_cell and south_aisle_cell.available ():
													self.borrowed_cells += [south_aisle_cell]
													south_aisle_cell.current_occupant = self

												mandatory_delay += max (self.AA (), self.SA (), self.SS ()) + \
														self.SA () + self.AS () + max (self.SA (), self.SS ()) + \
														max (self.SS (), self.SS (), self.AS ())
												self.personal_delay_counter += mandatory_delay
												next_cell.current_occupant.personal_delay_counter += mandatory_delay
												next_cell.connectors [self.next_direction].current_occupant.personal_delay_counter += mandatory_delay
												self.target.enter (self)
											else:
												self.needed_to_wait += 1
										else:
											debug (debugging.error, lambda: "%s: Too many people to handle crossing process" % str (self.location))

									else:
										#
										# Use the simple function for the number of spots to cross mid-seat.
										# First, though, we need the aisle to be available so that we can swap.
										#
									
										aisle_cell = self.location.connectors [opposite (self.next_direction)]
									
										if aisle_cell.available () and self.target.available () and \
												next_cell.current_occupant.personal_delay_counter == 0:
											aisle_cell.current_occupant = self
											self.borrowed_cells += [aisle_cell, self.location]
											mandatory_delay = max (self.SA (), self.SS ()) + self.SA () + self.AS () + max (self.SS (), self.AS ())
											self.personal_delay_counter += mandatory_delay + self.SS ()
											next_cell.current_occupant.personal_delay_counter += mandatory_delay + self.SS ()
											self.target.enter (self)
										else:
											self.needed_to_wait += 1
				
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
		
		def __init__ (self, rows, file, bin_capacity, bin_load_delay_function, bin_row_span):
			last_bin = luggage_bin (bin_capacity, bin_load_delay_function)
			self.head = node (0, file, last_bin)
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

				n = node (i, file, last_bin)
				p.connect (directions.south, n)
				self.nodes += n,
				p = n

			self.tail = n

		def add_window_row (self, row, direction, files, major_file):
			#
			# Returns the window seat.
			#
			
			base = self.nodes [row]
			
			for i in range (files):
				base = base.connect (direction, node (row, self.file + (i+1) * ordinal (direction), None))
				base.major_file = major_file

			return base

		def add_bridge_row (self, bridged_aisle, row, direction, files, major_file):
			#
			# Returns the seat in the bridged aisle to which this aisle connects.
			#

			return self.add_window_row (row, direction, files, major_file).connect ( \
					direction, bridged_aisle.nodes [row])

	class grid_plane_geometry:
		def __init__ (self, rows, file_count_list, \
				row_select_function, number_of_bags_function, SS, AS, SA, AA, bin_capacity, \
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

			self.aisles = [aisle (rows + 1, sum (file_count_list [0:i+1]) + i, \
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
					self.aisles [aisle_index], 0, directions.east, file_count_list [aisle_index], aisle_index)

			for row in range (1, rows + 1):
				#
				# First, connect all of the aisles together east-west.
				#

				self.aisles [0].add_window_row (row, directions.west, file_count_list [0], 0)

				for aisle_index in range (1, len (self.aisles)):
					self.aisles [aisle_index - 1].add_bridge_row ( \
						self.aisles [aisle_index], row, directions.east, file_count_list [aisle_index], aisle_index)

				self.aisles [len (self.aisles) - 1].add_window_row (row, directions.east, file_count_list [len (file_count_list) - 1], len (self.aisles))

				#
				# Next, put a passenger in each seat.
				# However, we're using the filter-lambda combination to eliminate aisle seats
				# from that list (those being ones with north or south connections).
				#

				self.passengers += [boarder (boarder.pre_boarding, x, number_of_bags_function (), \
						self.aisles, SS, AS, SA, AA) \
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
			return self.upper_geometry.start_location.available () and \
				   self.lower_geometry.start_location.available ()

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
			return self.entrance.current_occupant == None

	class simulation:
		def __init__ (self, plane, boarding_function):
			self.plane = plane
			self.boarding_function = boarding_function

		def run (self, passenger_selector_function = lambda p: True, boarding_delay_function = lambda: 8, time_step = 1):
			time = 0
			iterations = 0
			next_boarding = 0

			debug (debugging.status, lambda: "Beginning simulation...")
			debug (debugging.not_looped, lambda: str (self.plane) + "\n")

			currently_unboarded = self.plane.passengers
			currently_unfinished = []

			queue = []

			while len (currently_unfinished) or len (currently_unboarded) > 0 or len (queue) > 0:
				iterations += 1

				if debugging.tracing and iterations % 1 == 0:
					debug (debugging.quite_verbose, lambda: self.plane.compact_representation () + "\n" + str (int (time)) + "\n")

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
				else:
					debug (debugging.quite_verbose, lambda: "")

				#
				# The plane will decide how to board queued passengers.
				#

				if len (queue) > 0 and self.plane.available () and time > next_boarding:
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
					next_boarding = time + boarding_delay_function ()
				else:
					debug (debugging.quite_verbose, lambda: "")

				time += time_step

				delete_necessary = False
				for p in currently_unfinished:
					p.personal_delay_counter -= time_step
					
					if p.personal_delay_counter < 0:
						p.personal_delay_counter = 0

					p.step ()

					if p.finished ():
						delete_necessary = True
				
				if delete_necessary:
					copy = currently_unfinished
					
					for p in copy:
						if p.finished ():
							currently_unfinished.remove (p)

			return time

#
# Planes
#

	class airbus_320 (single_entrance_manager, grid_plane_geometry):
		name = "airbus-320"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			grid_plane_geometry.__init__ (self, 23, (3, 3), \
					lambda row: True, number_of_bags_function, SS, AS, SA, AA, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	S1 = airbus_320

	class boeing_767_200 (single_entrance_manager, combined_plane_geometry):
		name = "boeing-767-200"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			combined_plane_geometry.__init__ (self, \
					grid_plane_geometry (8, (2, 2, 2), \
							lambda row: True, number_of_bags_function, SS, AS, SA, AA, 8, bin_load_delay_function, 3), \
					grid_plane_geometry (25, (2, 3, 2), \
							lambda row: True, number_of_bags_function, SS, AS, SA, AA, 8, bin_load_delay_function, 3))

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	S2 = boeing_767_200

	class boeing_767_400 (single_entrance_manager, combined_plane_geometry):
		name = "boeing-767-400"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			combined_plane_geometry.__init__ (self, \
					grid_plane_geometry (8, (2, 2, 2), \
							lambda row: True, number_of_bags_function, SS, AS, SA, AA, 8, bin_load_delay_function, 3), \
					grid_plane_geometry (25, (2, 3, 2), \
							lambda row: True, number_of_bags_function, SS, AS, SA, AA, 8, bin_load_delay_function, 3))

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	M1 = boeing_767_400

	class airbus_a300_600 (single_entrance_manager, grid_plane_geometry):
		name = "airbus-a300-600"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			grid_plane_geometry.__init__ (self, 50, (2, 4, 2), \
					lambda row: True, number_of_bags_function, SS, AS, SA, AA, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	M2 = airbus_a300_600

	class boeing_747 (single_entrance_manager, grid_plane_geometry):
		name = "boeing-747"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			grid_plane_geometry.__init__ (self, 40, (3, 4, 3), \
					lambda row: True, number_of_bags_function, SS, AS, SA, AA, 4, bin_load_delay_function, 2)

			single_entrance_manager.__init__ (self, self.aisles [0].head)

	L1 = boeing_747

	class airbus_380 (single_entrance_manager, two_floor_plane_geometry):
		name = "airbus-380"

		def __init__ (self, number_of_bags_function, bin_load_delay_function, SS, AS, SA, AA):
			two_floor_plane_geometry.__init__ (self, \
					grid_plane_geometry (40, (3, 4, 3), \
						lambda row: True, number_of_bags_function, SS, AS, SA, AA, 4, bin_load_delay_function, 2), \
					grid_plane_geometry (30, (2, 4, 2), \
						lambda row: True, number_of_bags_function, SS, AS, SA, AA, 4, bin_load_delay_function, 2), \
					SS)

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

	def plane_generator (plane, r, SS, AS, SA, AA, bin_load_delay):
		return plane (	number_of_bags_function			= lambda: r.randint (0, 2), \
						bin_load_delay_function			= lambda t, c: t**0.5 * r.gauss (bin_load_delay, bin_load_delay / 6.0), \
						SS								= SS,
						AS								= AS,
						SA								= SA,
						AA								= AA)

	def run_single_simulation ():
		r = Random ()

		debugging.current_debug = debugging.very_verbose
		debugging.tracing = True

		debug (debugging.status, lambda: "Building aircraft model and passenger list...")
		debug (debugging.output, lambda: "Simulation: boarding took %s units of time." % \
				simulation (plane_generator (S2, r, \
						lambda: r.gauss (7.0, 2.0), \
						lambda: r.gauss (3.0, 0.8), \
						lambda: r.gauss (3.5, 0.4), \
						lambda: r.gauss (2.0, 0.3), \
						3.0), \
					boarding_function = staggered_adapter (reverse_block_loader)).run ( \
						passenger_selector_function		= lambda passenger: True, \
						boarding_delay_function			= lambda: r.gauss (7.0, 1.0), \
						time_step						= 0.5))

	def run_statistical_batch_simulation (planes, sensitivity_test_levels, how_many_adapters = 1, trial_count = 200):
		r = Random ()

		debugging.current_debug = debugging.error
		debugging.tracing = False

		boarding_functions = (reverse_block_loader, rotating_block_loader, random_loader, reverse_pyramid_loader, outside_in_loader)
		adapters = [identity_adapter, even_odd_adapter, staggered_adapter][:how_many_adapters]
		
		adjustable_parameters = (7.0, 3.0, 3.5, 2.0, 2.0, 0.8, 0.4, 0.3, 2.0, 7.0)

		possibilities = [[1.0, 1.0, 1.0, 1.0, 1.0, d] for d in sensitivity_test_levels.keys ()] + \
						[[1.0, 1.0, 1.0, 1.0, c, 1.0] for c in sensitivity_test_levels.keys ()] + \
						[[1.0, 1.0, 1.0, b, 1.0, 1.0] for b in sensitivity_test_levels.keys ()] + \
						[[1.0, 1.0, a, 1.0, 1.0, 1.0] for a in sensitivity_test_levels.keys ()] + \
						[[1.0, x, 1.0, 1.0, 1.0, 1.0] for x in sensitivity_test_levels.keys ()] + \
						[[y, 1.0, 1.0, 1.0, 1.0, 1.0] for y in sensitivity_test_levels.keys ()]

		if len (possibilities) == 0:
			possibilities = [[1.0] * 6]
			sensitivity_test_levels = {1.0: 'n'}
		else:
			sensitivity_test_levels[1.0] = 'n'

		possibility_description = lambda p: sensitivity_test_levels[p[0]] + sensitivity_test_levels[p[1]] + \
											sensitivity_test_levels[p[2]] + sensitivity_test_levels[p[3]] + \
											sensitivity_test_levels[p[4]] + sensitivity_test_levels[p[5]]

		trials_per_configuration = trial_count
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
						debug (debugging.status, lambda: "%s_%s\n" % (a.name, b.name))
						
				current_file.write ("\n")
				
				for trial in range (trials_per_configuration):
					for a in adapters:
						for b in boarding_functions:
							immediate_result = str (simulation ( \
									plane = plane_generator (plane, r, \
										lambda: r.gauss (adjustable_parameters [0] * possibility [0], adjustable_parameters [4] * possibility [0]), \
										lambda: r.gauss (adjustable_parameters [1] * possibility [1], adjustable_parameters [5] * possibility [1]), \
										lambda: r.gauss (adjustable_parameters [2] * possibility [2], adjustable_parameters [6] * possibility [2]), \
										lambda: r.gauss (adjustable_parameters [3] * possibility [3], adjustable_parameters [7] * possibility [3]), \
										adjustable_parameters [8] * possibility [4]), \
									boarding_function = a (b)).run ( \
										passenger_selector_function		= lambda passenger: True, \
										boarding_delay_function			= lambda: \
											r.gauss (adjustable_parameters [9] * possibility [5], possibility [5]), \
										time_step						= time_step))

							current_file.write (immediate_result + "\t")
							debug (debugging.status, lambda: immediate_result + "\n")

					current_file.write ("\n")
					current_file.flush ()
					debug (debugging.status, lambda: "\n")

				current_file.close ()

	run_single_simulation ()
#	run_statistical_batch_simulation ([L2], {}, 3, 200)
#	run_statistical_batch_simulation ([S1, S2, M1, M2, L1, L2], {0.5: 'l', 1.75: 'h'}, 1, 25)

main ()
