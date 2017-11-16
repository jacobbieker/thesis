import numpy as np
import pickle
import pandas as pd
import sys
import matplotlib.pyplot as plt

# Matrix for converting axial coordinates to pixel coordinates
axial_to_pixel_mat = np.array([[np.sqrt(3), np.sqrt(3) / 2], [0, 3 / 2.]])

# Matrix for converting pixel coordinates to axial coordinates
pixel_to_axial_mat = np.linalg.inv(axial_to_pixel_mat)

# These are the vectors for moving from any hex to one of its neighbors.
SE = np.array((1, 0, -1))
SW = np.array((0, 1, -1))
W = np.array((-1, 1, 0))
NW = np.array((-1, 0, 1))
NE = np.array((0, -1, 1))
E = np.array((1, -1, 0))
ALL_DIRECTIONS = np.array([NW, NE, E, SE, SW, W, ])

# Conversion Functions ######

def cube_to_axial(cube):
    """
    Convert cube to axial coordinates.
    :param cube: A coordinate in cube form. nx3
    :return: `cube` in axial form.
    """
    return np.vstack((cube[:, 0], cube[:, 2])).T


def axial_to_cube(axial):
    """
    Convert axial to cube coordinates.
    :param axial: A coordinate in axial form.
    :return: `axial` in cube form.
    """
    x = axial[:, 0]
    z = axial[:, 1]
    y = -x - z
    cube_coords = np.vstack((x, y, z)).T
    return cube_coords


def axial_to_pixel(axial, radius):
    """
    Converts the location of a hex in axial form to pixel coordinates.
    :param axial: The location of a hex in axial form. nx3
    :param radius: Radius of all hexagons.
    :return: `axial` in pixel coordinates.
    """
    pos = radius * axial_to_pixel_mat.dot(axial.T)
    return pos.T


def cube_to_pixel(cube, radius):
    """
    Converts the location of a hex in cube form to pixel coordinates.
    :param cube: The location of a hex in cube form. nx3
    :param radius: Radius of all hexagons.
    :return: `cube` in pixel coordinates.
    """
    in_axial_form = cube_to_axial(cube)
    return axial_to_pixel(in_axial_form, radius)


def pixel_to_cube(pixel, radius):
    """
    Converts the location of a hex in pixel coordinates to cube form.
    :param pixel: The location of a hex in pixel coordinates. nx2
    :param radius: Radius of all hexagons.
    :return: `pixel` in cube coordinates.
    """
    axial = pixel_to_axial_mat.dot(pixel.T) / radius
    return axial_to_cube(axial.T)


def pixel_to_axial(pixel, radius):
    """
    Converts the location of a hex in pixel coordinates to axial form.
    :param pixel: The location of a hex in pixel coordinates. nx2
    :param radius: Radius of all hexagons.
    :return: `pixel` in axial coordinates.
    """
    cube = pixel_to_cube(pixel, radius)
    return cube_to_axial(cube)


def cube_round(cubes):
    """
    Rounds a location in cube coordinates to the center of the nearest hex.
    :param cubes: Locations in cube form. nx3
    :return: The location of the center of the nearest hex in cube coordinates.
    """
    rounded = np.zeros((cubes.shape[0], 3))
    rounded_cubes = np.round(cubes)
    for i, cube in enumerate(rounded_cubes):
        (rx, ry, rz) = cube
        xdiff, ydiff, zdiff = np.abs(cube-cubes[i])
        if xdiff > ydiff and xdiff > zdiff:
            rx = -ry - rz
        elif ydiff > zdiff:
            ry = -rx - rz
        else:
            rz = -rx - ry
        rounded[i] = (rx, ry, rz)
    return rounded


def axial_round(axial):
    """
    Rounds a location in axial coordinates to the center of the nearest hex.
    :param axial: A location in axial form. nx2
    :return: The location of the center of the nearest hex in axial coordinates.
    """
    return cube_to_axial(axial_to_cube(axial))

class HexTile(object):
    """
    Base Hex class. Doesn't do anything. Ideally, you want to store instances of
    a subclass of this tile in a HexMap object.
    """

    def __init__(self, axial_coordinates, radius, tile_id):
        super(HexTile, self).__init__()
        self.axial_coordinates = np.array([axial_coordinates])
        self.cube_coordinates = axial_to_cube(self.axial_coordinates)
        self.position = axial_to_pixel(self.axial_coordinates, radius)
        self.radius = radius
        self.tile_id = tile_id

# These are the vectors for moving from any hex to one of its neighbors.

def cube_to_oddr(cube):
    col = cube[0] + (cube[1] - (cube[1] & 1)) / 2
    row = cube[1]
    return [col, row]

def oddr_to_cube(hex):
    x = hex[0] - (hex[1] - (int(hex[1]) & 1)) / 2
    z = hex[1]
    y = -x-z
    return [x, y, z]

from fact.instrument import get_pixel_coords, get_pixel_dataframe, constants

PIXEL_RADIUS = constants.PIXEL_SPACING_IN_MM / 2
position_dict = {}
x = []
y = []
z = []

#plt.show()

pm = get_pixel_dataframe()
print(pm)

axial_x_cor = pm['pos_X'].values
axial_y_cor = pm['pos_Y'].values
chids = pm['CHID'].values

all_hexes = []

for element in chids:
    hex = HexTile((axial_x_cor[element], axial_y_cor[element]), PIXEL_RADIUS, element)
    all_hexes.append(hex)


for hexagon in all_hexes:
    x.append(hexagon.cube_coordinates[0][0])
    y.append(hexagon.cube_coordinates[0][1])
    z.append(hexagon.cube_coordinates[0][2])

# Get the largest and smallest values in every direction
start_y = np.min(y)
end_y = np.max(y)
start_x = np.min(x)
end_x = np.max(x)
start_z = np.min(z)
end_z = np.max(z)

x_box = np.linspace(start_y, end_y, 5)
y_box = np.linspace(start_x, end_x, 5)
z_box = np.linspace(start_z, end_z, 5)
xx, yy, zz = np.meshgrid(x_box, y_box, z_box)

from mpl_toolkits.mplot3d import Axes3D
fig = plt.figure()
fig.suptitle("FACT Camera in Cubic coordinates")
ax = fig.add_subplot(111, projection='3d')

ax.scatter(xx, yy, zz, c='g')
mapping = np.arange(0, 1440, 1)
ax.scatter(x, y, z, c=mapping, cmap=plt.cm.Reds, marker='h')

ax.set_xlabel('X Position')
ax.set_ylabel('Y Position')
ax.set_zlabel('Z Position')

plt.show()

flat_x = []
flat_y = []
for hexagon in all_hexes:
    flat_x.append(hexagon.position[0][0])
    flat_y.append(hexagon.position[0][1])
    print(hexagon.position[0])

plt.scatter(flat_x, flat_y, marker='h')
plt.title('Raw Position Coordinates')
plt.show()

flat_x = []
flat_y = []
for hexagon in all_hexes:
    flat_x.append(hexagon.axial_coordinates[0][0])
    flat_y.append(hexagon.axial_coordinates[0][1])

plt.scatter(flat_x, flat_y, marker='h')
plt.title('Axial Coordinates')
plt.show()

flat_x = []
flat_y = []
for hexagon in all_hexes:
    flat_x.append(hexagon.position[0][0])
    flat_y.append(hexagon.position[0][1])
    print(hexagon.position[0])

flat_x = np.asarray(flat_x)
flat_y = np.asarray(flat_y)

x_cor, y_cor = get_pixel_coords()

plt.scatter(x_cor, y_cor, marker='h')
plt.title('Raw Pixel Coordinates')
plt.show()

flat_y=np.round(flat_y/8.2175,0)
flat_x=flat_x/4.75+flat_y
mapping = np.arange(0, 1440, 1)
plt.scatter(flat_x, flat_y, c=mapping, cmap=plt.cm.Reds, marker='h')
plt.xlabel('X Position')
plt.ylabel('Y Position')
plt.title('FACT Camera skewed to quadratic pixels')

plt.show()


#TODO Need to convert the pixel corrdinates to the hexagon coordinates first, then hexagon to cubes

#Haveto convert the  coordinates toe hexagonal