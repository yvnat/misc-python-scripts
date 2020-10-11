########################################################################
#
# A 2D terrain generation and exploration game
#
# Move with arrow keys, quit with q
#
########################################################################

import random
from time import sleep

import numpy as np
import noise
import curses

random.seed()

CHUNK_SIZE = 16
GROUND_LEVEL = 8	#the base ground level
GROUND_HEIGHT = 30
GROUND_SCALE = .02
CAVE_SCALE = .03
CAVE_WIDTH = .15
ORE_SCALE = .1
ORE_THRESHOLD = .7
WATER_LEVEL = 8

class Chunk:
	def val_to_ascii(self, val):
		if val == 0:	#sky
			return '░'
		if val == 1:	#rock
			return '▓'
		if val == 2:	#cave air
			return '░'
		if val == 3:	#ore
			return '£'
		if val == 4:	#water
			return '≈'
		if val == 5:	#grass
			return '▒'
		return '?'		#unknown block

	def __init__(self, x, y, gen):
		self.blocks = np.zeros((CHUNK_SIZE, CHUNK_SIZE))
		self.x = x
		self.y = y
		self.modified = False
		for in_y in range(0, self.blocks.shape[1]):
			for in_x in range(0, self.blocks.shape[0]):
				self.blocks[in_x, in_y] = gen(in_x + (self.x*16), 
											  in_y + (self.y*16))
				if (in_y > 0 and self.blocks[in_x, in_y - 1] == 0 
					and (self.blocks[in_x, in_y] == 1)):
					#if below air and is stone, turn to grass
					self.blocks[in_x, in_y] = 5	#grass

	def render(self, camerax, cameray, offsetx, offsety, drawfunc):
		for y in range(0, self.blocks.shape[1]):
			for x in range(0, self.blocks.shape[0]):
				drawy = y - cameray + offsety + self.y*16
				drawx = x - camerax + offsetx + self.x*16
				val = self.blocks[x, y]
				drawfunc(drawy, drawx, self.val_to_ascii(val), val)
				

class Display:
	def __init__(self):
		#initialize curses
		self.stdscr = curses.initscr()
		curses.start_color()
		curses.noecho()	#this makes keypresses not show up on screen
		curses.cbreak()	#allows instant reaction to keypresses without enter
		self.stdscr.nodelay(True)
		self.stdscr.keypad(True)

		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_CYAN)
		# curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_MAGENTA)
		curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(4, curses.COLOR_RED, curses.COLOR_WHITE)
		curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLUE)
		curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_YELLOW)

		#set the seed
		self.seed = random.random() * 100000000
		#create the dictionary of chunks
		self.chunks = {}
		self.chunks_to_unload = []
		self.playerx = 0
		self.playery = 0
		for x in range(-3, 3):
			for y in range(-3, 3):
				self.add_chunk(x,y)

	def chunk_generator(self, x, y):
		"""Determine the terrain for a given coordinate. Passed to chunks."""
		ground_level = ((GROUND_HEIGHT 
						* noise.snoise2(x*GROUND_SCALE, self.seed, 5))
						+ GROUND_LEVEL)
		cave_value = noise.snoise3(x*CAVE_SCALE, y*CAVE_SCALE, self.seed)
		ore_value = noise.snoise3(x*ORE_SCALE, y*ORE_SCALE, self.seed)
		# print(ground_level)
		if y < ground_level:
			if (y < WATER_LEVEL):
				return 0	#sky
			return 4	#water
		if cave_value < .5 + CAVE_WIDTH and cave_value > .5 - CAVE_WIDTH:
			return 2	#cave air
		if ore_value > ORE_THRESHOLD:
			return 3	#ore
		return 1	#rock

	def is_passable_block(self, blockID, gravity):
		return blockID == 0 or ((not gravity) and blockID == 4) or blockID == 2

	def add_chunk(self, x, y):
		"""Add a chunk to the dictionary."""
		self.chunks[(x,y)] = Chunk(x,y, self.chunk_generator)

	def addch_wrapper(self, y, x, char, colour):
		"""A wrapper for addch that is passed to chunks for rendering"""
		if ((x < 1 or x >= curses.COLS - 1)
			or (y < 1 or y >= curses.LINES - 1)):
			#if either x or y are out of bounds, do nothing
			return
		self.stdscr.addch(int(y), int(x), char, curses.color_pair(int(colour) + 1))

	def kings_distance(self, x1, y1, x2, y2):
		"""return taxicab distance between two points"""
		return max(abs(x1 - x2), abs(y1 - y2))

	def render(self, x, y, offsetx, offsety):
		"""render terrain centered around (x,y), offset by (offsetx,offsety)"""
		self.stdscr.clear()
		for i in self.chunks.values():
			i.render(x, y, offsetx, offsety, self.addch_wrapper)
		self.addch_wrapper(offsety, offsetx, '@', 2)
		self.stdscr.addstr(0, 0, "meenman v0.1 [q] to quit")
		self.stdscr.refresh()

	def handle_chunk_loading(self, x, y, render_distance):
		#unload far away chunks
		for i in self.chunks.values():
			if self.kings_distance(x / 16, y / 16, i.x, i.y) > render_distance:
				self.chunks_to_unload.append(i)
		while len(self.chunks_to_unload) != 0:
			del self.chunks[(self.chunks_to_unload[-1].x, 
							 self.chunks_to_unload[-1].y)]
			del self.chunks_to_unload[-1]
		for i in range(-render_distance, render_distance):
			for j in range(-render_distance, render_distance):
				if not self.chunks.__contains__((int(x/16) + j, int(y/16) + i)):
					self.add_chunk(int(x/16) + j, int(y/16) + i)

	def move_player(self, x, y, g=False):
		chunk = self.chunks[((self.playerx+x) // 16, (self.playery+y) // 16)]
		internal_x = (self.playerx + x) % 16
		internal_y = (self.playery + y) % 16
		if self.is_passable_block(chunk.blocks[internal_x, internal_y], g):
			self.playerx += x
			self.playery += y
		elif x != 0 and y == 0:	#if moving horizontally and hitting wall, try climb
			self.move_player(x, -1)

	def loop(self):
		run = True
		while run:
			key = self.stdscr.getch()
			self.move_player(0,1, g=True)
			while (key != -1):
				if key == 113:
					run = False
					print("quitting")
				if key == curses.KEY_LEFT:
					self.move_player(-1, 0)
				if key == curses.KEY_RIGHT:
					self.move_player(1, 0)
				if key == curses.KEY_UP:
					self.move_player(0, -3)
				if key == curses.KEY_DOWN:
					self.move_player(0, 1)
				key = self.stdscr.getch()
			self.handle_chunk_loading(self.playerx, self.playery, 3)
			self.render(self.playerx, self.playery, curses.COLS//2, curses.LINES//2)

	def __del__(self):
		curses.nocbreak()
		self.stdscr.keypad(False)
		curses.echo()
		curses.endwin()
		self.stdscr.nodelay(False)
		print("well deleted")

d = Display()
d.loop()