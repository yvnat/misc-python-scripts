########################################################################
#
# A simple erosion simulator
#
# Simulates the erosion of a perlin noise terrain using simulated raindrops
#
# Non-interactive
#
########################################################################

import random
from time import sleep

import numpy as np
from opensimplex import OpenSimplex
import pygame

EROSION_STRENGTH = .01
SEDIMENTATION_STRENGTH = .1
DROP_CAPAC = 1
STEEPNESS_COEFF = 1
MAX_SED_PER_TILE = 1

class Console:
	#A basic graphical ASCII output emulator
	#In practice, only the character " " (space) is ever printed
	#initializer
	def __init__(self, x, y, scale):
		pygame.init()
		pygame.font.init()
		self.font = pygame.font.SysFont('Unifont', scale)
		self.size = self.width, self.height = x*scale, y*scale
		self.x = x
		self.y = y
		self.scale = scale
		self.screen = pygame.display.set_mode(self.size)
	#helpers and debugging
	def test(self):
		for i in range(self.y):
			for j in range(self.x):
				self.draw_char(j, i, chr(self.get_valid_char(32, 5000)), 
							(255 * random.random(), 255 * random.random(), 255 * random.random()))
		self.render()
	def get_percent_on(self, unicode_value):
		surf = self.font.render(chr(unicode_value), False, (255,255,255))
		size = surf.get_size()
		num_empty = 0
		for i in range(size[1]):
			for j in range(size[0]):
				num_empty += (surf.get_at((j,i)) == (0, 0, 0, 255))
		return ((size[0] * size[1]) - num_empty) / (size[0] * size[1])
	def is_valid_character(self, unicode_value):
		percent = self.get_percent_on(unicode_value)
		return percent > .05 and percent < .5
	#interface methods
	def get_valid_char(self, lower_bound, upper_bound, seed=-1):
		if seed != -1:
			random.seed(seed)
		char = int((upper_bound - lower_bound) * random.random()) + lower_bound
		while not self.is_valid_character(char):
			char = int((upper_bound - lower_bound) * random.random()) + lower_bound
		return char
	def draw_char(self, x, y, char, fore=(255,255,255), back = (0,0,0)):
		surf = self.font.render(char, False, fore)
		pygame.draw.rect(self.screen,back,(x * self.scale,y * self.scale, self.scale, self.scale))
		self.screen.blit(surf, (x * self.scale,y * self.scale))
	def render(self):
		pygame.display.flip()

class TerrainColumn:
	def __init__(self, height):
		self.rock_depth = height
		self.sediment_depth = 0

	def erode(self, depth):
		"""erode to a given depth, removing sediment first"""
		self.sediment_depth -= depth
		if (self.sediment_depth < 0):
			self.rock_depth += self.sediment_depth
			self.sediment_depth = 0
		if self.rock_depth <= 0:
			self.rock_depth = 1
	
	def deposit(self, depth):
		self.sediment_depth += depth

	def height(self):
		"""Return the total height of the column"""
		return self.rock_depth + self.sediment_depth

	def sediment_to_ascii(self):
		# if self.sediment_depth < 4:
		# 	return " "
		# elif self.sediment_depth < 8:
		# 	return "`"
		# elif self.sediment_depth < 12:
		# 	return "\""
		# elif self.sediment_depth < 16:
		# 	return "░"
		# elif self.sediment_depth < 20:
		# 	return "▒"
		# return "▓"
		return " "
		
	def height_to_colour(self):
		value = self.height()
		# print(int(255*(value/100)), int(255*(value/100)), int(255*(value/100)))
		return (max(int(255*min(1, (value/100))), 0), max(int(255*min(1, (value/100))), 0), max(int(255*min(1, (value/100))), 0))

class ErosionDrop:
	def __init__(self, x, y):
		self.x = x
		self.y = y
		self.sediment = 0
		self.sediment_capacity = DROP_CAPAC

class MapGen:
	def noise_octaves(self, x, y, additional_octaves = 0, pers = 2):
		value = self.gen.noise2d(x, y)
		max_value = 1
		for i in range(additional_octaves):
			amp = (1/(pers**i))
			value += amp*self.gen.noise2d(x*(2**i), y*(2**i))
			max_value += amp
		return value/max_value

	def __init__(self, seed, x, y):
		self.console = Console(x, y, 8)
		self.gen = OpenSimplex(seed=seed)
		self.map = np.ndarray((x, y), dtype=TerrainColumn)
		for i in range(self.map.shape[0]):
			for j in range(self.map.shape[1]):
				self.map[i, j] = TerrainColumn(int(self.noise_octaves(i/10, j/10, 0)*30 + 40))

	def find_downhill_vector_steepness(self, x, y):
		lowest = 1000000
		vector = (0,0)
		for i in range(-1, 2):
			for j in range(-1, 2):
				if ((x + i < 0 or x + i >= self.map.shape[0]) 
					or (y + j < 0 or y + j >= self.map.shape[1])):
					#if next to border, dont move
					return [(0,0), 0]
				current_height = self.map[x + i, y + j].height()
				if (i != 0 and j != 0):
					#must be at least 1 = 0
					# continue
					current_height *= 1.4
				if current_height < lowest:
					lowest = self.map[x + i, y + j].height()
					vector = (i,j)
		return [vector, self.map[x, y].height() - lowest]

	def handle_sediment(self, drop, erosion_mesh, steepness):
		"""pick up sediment if not at full capacity, deposit sediment otherwise"""
		if drop.sediment <= drop.sediment_capacity - EROSION_STRENGTH:
			sediment_taken = ((drop.sediment_capacity - drop.sediment) 
							  * EROSION_STRENGTH * steepness**STEEPNESS_COEFF)
			drop.sediment += sediment_taken
			erosion_mesh[drop.x, drop.y, 0] += sediment_taken
		elif drop.sediment >= SEDIMENTATION_STRENGTH:
			drop.sediment -= SEDIMENTATION_STRENGTH
			erosion_mesh[drop.x, drop.y, 1] += SEDIMENTATION_STRENGTH
			
	def drop_all_sediment(self, drop, erosion_mesh):
		erosion_mesh[drop.x, drop.y, 1] += drop.sediment#/1.5
		drop.sediment = 0

	def simulate_erosion_drop(self, x, y, erosion_mesh):
		drop = ErosionDrop(x, y)
		vector = (-1, -1)
		path_length = 0
		while (vector != (0,0) and 
				path_length < max(erosion_mesh.shape[0], erosion_mesh.shape[1])):
			#path length prevents infinite loops
			vs = self.find_downhill_vector_steepness(drop.x, drop.y)
			vector = vs[0]
			steepness = vs[1]
			self.handle_sediment(drop, erosion_mesh, steepness)
			drop.x += vector[0]
			drop.y += vector[1]
		self.drop_all_sediment(drop, erosion_mesh)

	def erosion_cycle(self, iterations):
		erosion_mesh = np.zeros((self.map.shape[0], self.map.shape[1], 2))
		for i in range(iterations):
			self.simulate_erosion_drop(int(random.random() * self.map.shape[0]),
									   int(random.random() * self.map.shape[1]),
									   erosion_mesh)
		for i in range(self.map.shape[0]):
			for j in range(self.map.shape[1]):
				self.map[i, j].erode(erosion_mesh[i,j, 0])
				self.map[i, j].deposit(min(MAX_SED_PER_TILE, erosion_mesh[i,j, 1]))

	def erode_landscape(self, cycles, iterations_per_cycle):
		for i in range(cycles):
			self.erosion_cycle(iterations_per_cycle)
			self.print_self()
			print("iteration", i, "of", cycles)
			for event in pygame.event.get():
				if event.type == pygame.QUIT: return

	def print_self(self):
		for i in range(self.map.shape[0]):
			for j in range(self.map.shape[1]):
				self.console.draw_char(i, j, self.map[i, j].sediment_to_ascii(), fore=(255,0,0), back=self.map[i, j].height_to_colour())
		self.console.render()

g = MapGen(int(random.random()*1000000), 50, 50)
g.erode_landscape(120, 2000)
g.print_self()
input("input anything to the terminal to exit")