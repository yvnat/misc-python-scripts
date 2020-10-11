########################################################################
#
# Simulates gravity and inelastic collisions between bodies
#
# The user controls a ship (red), also affected by these forces, using WASD
#
########################################################################

import math
import random
from time import sleep
from itertools import combinations

import pygame

GRAV_CONST = 1.5    #gravitational constant, G, for the simulation
MIN_DIST = .0001    #the minimum distance or radius, to stop divide by 0
PLANET_SIZE_COEFF = 10 #the coefficient for planet sizes

class PhysicsObject:
    """
    Base class for an object that follows newtonian physics in 2D space.

    Instance Variables:
    mass-- the mass of the object, as a float.
    radius-- the radius of the object, as a float.
    pos-- the position of the object, as a tuple of floats (x,y).
    vel-- the current velocity of the object in component form, 
          as a tuple of floats (x,y).

    Public Methods:
    apply_force()
    move()
    """

    def __init__(self, mass, pos, radius=100.0, vel=(0.0,0.0)):
        """
        Construct a PhysicsObject of given properties.

        Keyword arguments:
        mass-- the mass of the object, as a float.
        pos-- the starting position of the object, as a 
              tuple of floats (x,y).
        radius-- the radius of the object, as a float. Defaults to 100.0
        vel-- the starting velocity of the object in component form, 
              as a tuple of floats (x,y). Defaults to (0.0,0.0).
        """
        self.mass = mass
        self.radius = radius
        self.pos = pos
        self.vel = vel

    def apply_force(self, force): #force must be given in (x,y)
        """Apply a force on the object and thus accelerate it.
        
        Keyword arguments:
        force-- the force applied in component form, 
                as a tuple of floats (x,y)
        """
        self.vel = (self.vel[0] + (force[0] / self.mass), 
                    self.vel[1] + (force[1] / self.mass))

    def move(self):
        """Move the object based on current velocity."""
        self.pos = (self.pos[0] + self.vel[0], 
                    self.pos[1] + self.vel[1])


class Planet(PhysicsObject):
    """
    Child class of PhysicsObject, with automatic radius.
    """
    
    def __init__(self, mass, pos, vel=(0.0,0.0)):
        #assume that mass is proportional to volume to derive radius
        radius = PLANET_SIZE_COEFF * mass**(1/3)
        super().__init__(mass, pos, radius, vel)


class Propulsive(PhysicsObject):
    def __init__(self, mass, pos, radius=100.0, vel=(0.0,0.0)):
        super().__init__(mass, pos, radius, vel)
        self.thrust = (0.0, 0.0)
    
    def move(self):
        """
        Accelerate from thrust, then move
        
        Overriding the PhysicsObject move() method
        """
        self.vel = (self.vel[0] + (self.thrust[0] / self.mass), 
                    self.vel[1] + (self.thrust[1] / self.mass))
        self.pos = (self.pos[0] + self.vel[0], 
                    self.pos[1] + self.vel[1])

    def accx(self, amount):
        """accelerate along the x axis"""
        self.thrust = (self.thrust[0] + amount, self.thrust[1])
    
    def accy(self, amount):
        """accelerate along the y axis"""
        self.thrust = (self.thrust[0], self.thrust[1] + amount)

class World:
    """
    Contains PhysicsObjects and handles their interactions

    Instance Variables:
    objects-- stores a list of PhysicsObjects

    Public Methods:
    simulate_tick()
    """

    def __init__(self):
        self.objects = [
                        Propulsive(.001, (1000, 2000), 10, (.6, 0.0)),
                        Planet(1000.0, (1000.0,1000.0), (0.6, 0.1)), Planet(10, (2000.0,1000.0), (0.0, .30)),
                        Planet(1000.0, (5000.0,1000.0), (-0.6, 0.1))
                        ]
        self.ship = self.objects[0]
        pass

    def _add_object(self, physobj):
        """Add the PhysicsObject physobj to self.objects"""
        self.objects.append(physobj)

    def _distance(self, pos1, pos2):
        """Return distance of two coordinate points in format (x,y)"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def _mutual_force(self, object1, object2, force):
        """
        Apply equal and opposite attractive forces between two PhysicsObjects.
        
        Keyword arguments:
        object1-- the first PhysicsObject
        object2-- the second PhysicsObject
        force-- the magnitude of the force, as a float, 
                with positive defined as pulling the objects together
        """
        distance = self._distance(object1.pos, object2.pos)
        if distance == 0: distance = MIN_DIST
        coeff = force/distance
        #this is the force applied on object2, in component form.
        force_components = ((object1.pos[0] - object2.pos[0]) * coeff,
                            (object1.pos[1] - object2.pos[1]) * coeff)
        # apply the forces (note that the force on object1 is 
        # equal and opposite to the force on object2)
        object2.apply_force(force_components)
        object1.apply_force((-force_components[0], -force_components[1]))
    
    def _apply_gravitational_force(self, object1, object2):
        """
        Calculate and apply the gravitational force between two objects
        
        Keyword arguments:
        object1-- the first PhysicsObject
        object2-- the second PhysicsObject
        """
        # F = G(m1*m2)/r^2
        radius = self._distance(object1.pos, object2.pos)
        if radius == 0: radius = MIN_DIST #stop div by 0 crashes
        force = GRAV_CONST * (object1.mass * object2.mass) / (radius)**2
        self._mutual_force(object1, object2, force)

    def _are_touching(self, object1, object2):
        """Return whether or not two objects are touching"""
        total_r = object1.radius + object2.radius
        return self._distance(object1.pos, object2.pos) <= total_r
    
    def _simulate_sticky_collision(self, obj1, obj2):
        """
        Simulate a sticky collision, replacing two objects with one
        
        Keyword arguments:
        obj1-- the first PhysicsObject involved in the collision
        obj2-- the second PhysicsObject involved in the collision
        """
        #conserve mass and area
        new_radius = math.sqrt((obj1.radius)**2 + (obj2.radius)**2)
        new_mass = obj1.mass + obj2.mass
        #positioned is average weighed (heh) by mass
        new_pos = ((obj1.pos[0]*obj1.mass + obj2.pos[0]*obj2.mass)/(new_mass),
                   (obj1.pos[1]*obj1.mass + obj2.pos[1]*obj2.mass)/(new_mass))
        #calculate the new velocity using momentum (split into x and y for clarity)
        vx = (obj1.vel[0]*obj1.mass + obj2.vel[0]*obj2.mass)/new_mass
        vy = (obj1.vel[1]*obj1.mass + obj2.vel[1]*obj2.mass)/new_mass
        new_vel = (vx, vy)
        #delete the two objects, create new one in its place
        self.objects.remove(obj1)
        self.objects.remove(obj2)
        self._add_object(PhysicsObject(new_mass, new_pos, new_radius, new_vel))
        print("collision between", obj1, obj2)

    def simulate_tick(self):
        """Simulate a single tick of physics simulation"""
        #first move all objects
        for i in self.objects:
            i.move()
        #then have all pairs of objects interact
        for pair in combinations(self.objects, 2):
            if self._are_touching(pair[0], pair[1]):
                self._simulate_sticky_collision(pair[0], pair[1])
            self._apply_gravitational_force(pair[0], pair[1])


class SimulationHandler:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.font = pygame.font.SysFont('Unifont', 32)
        self.size = self.width, self.height = 480, 360
        self.screen = pygame.display.set_mode(self.size)
        self.world = World()
        self.run = True
        self.camx = 0
        self.camy = 0

    def get_colour_of_obj(self, obj):
        if isinstance(obj, Planet):
            return (0, 255, 0)
        if isinstance(obj, Propulsive):
            return (255, 0, 0)
        return (128, 100, 128)

    def go(self):
        while self.run:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.run = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_a:
                        self.world.ship.accx(-.0001)
                    if event.key == pygame.K_d:
                        self.world.ship.accx(.0001)
                    if event.key == pygame.K_w:
                        self.world.ship.accy(-.0001)
                    if event.key == pygame.K_s:
                        self.world.ship.accy(.0001)
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_a:
                        self.world.ship.accx(.0001)
                    if event.key == pygame.K_d:
                        self.world.ship.accx(-.0001)
                    if event.key == pygame.K_w:
                        self.world.ship.accy(.0001)
                    if event.key == pygame.K_s:
                        self.world.ship.accy(-.0001)
            self.camx = self.width/2 - self.world.ship.pos[0]/10
            self.camy = self.height/2 - self.world.ship.pos[1]/10
            # print(self.camx, self.camy)
            self.screen.fill((0,0,0))
            for i in self.world.objects:
                pygame.draw.circle(self.screen, self.get_colour_of_obj(i), 
                    (int(i.pos[0] / 10 + self.camx), int(i.pos[1] / 10 + self.camy)), 
                    max(int(i.radius / 10), 1), 0)
            pygame.display.flip()
            sleep(.01)
            self.world.simulate_tick()


s = SimulationHandler()
s.go()