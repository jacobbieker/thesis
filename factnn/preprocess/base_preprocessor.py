import numpy as np
from fact.instrument import get_pixel_coords
import pickle
import os
import glob


class BasePreprocessor(object):

    def __init__(self, config):
        self.directories = config['directories']
        if 'paths' in config:
            self.paths = config['paths']
        else:
            # Get paths from the directories
            self.paths = []
            for directory in self.directories:
                for root, dirs, files in os.walk(self.directories):
                    for file in files:
                        if file.endswith("phs.jsonl.gz"):
                            self.paths.append(os.path.join(root, file))

        if 'dl2_file' in config:
            self.dl2_file = config['dl2_file']
        else:
            self.dl2_file = None

        if 'rebin_size' in config:
            if config['rebin_size'] <= 10:
                try:
                    self.rebinning = pickle.load(
                        os.path.join("factnn", "resources", "rebinning_" + config['rebin_size'] + ".p"))
                except:
                    self.rebinning = self.generate_rebinning(config['rebin_size'])
            else:
                self.rebinning = self.generate_rebinning(config['rebin_size'])
        else:
            self.rebinning = self.generate_rebinning(5)

        # Shape is used only to determine how much time information is kept, if negative, start from back, if positive from
        # front, range gives that range of time slices
        if 'shape' in config:
            self.start = config['shape'][0]
            self.end = config['shape'][1]
        else:
            # Get it from the rebinning
            self.end = 100
            self.start = 0

        self.shape = [-1, int(np.ceil(np.abs(186 * 2) / config['rebin_size'])), int(np.ceil(np.abs(186 * 2) / config['rebin_size'])), self.end - self.start]

        self.dataset = None
        if 'output_file' in config:
            self.output_file = config['output_file']
        else:
            self.output_file = None

    def init(self):
        return NotImplemented

    def generate_rebinning(self, size):
        new_x = []
        new_y = []

        x, y = get_pixel_coords()
        for i in range(1440):
            if i != 0:
                for j in range(i):
                    new_x.append(x[i])
                    new_y.append(y[i])
            else:
                new_x.append(x[0])
                new_y.append(y[0])

        from shapely.geometry import Point, Polygon, MultiPoint
        from shapely.affinity import translate

        p = Point(0.0, 0.0)
        PIXEL_EDGE = 9.51 / np.sqrt(3)
        # Top one
        p1 = Point(0.0, PIXEL_EDGE)
        # Bottom one
        p2 = Point(0.0, -PIXEL_EDGE)
        # Bottom right
        p3 = Point(-PIXEL_EDGE * (np.sqrt(3) / 2), -PIXEL_EDGE * .5)
        # Bottom left
        p4 = Point(PIXEL_EDGE * (np.sqrt(3) / 2), PIXEL_EDGE * .5)
        # right
        p5 = Point(PIXEL_EDGE * (np.sqrt(3) / 2), -PIXEL_EDGE * .5)
        #  left
        p6 = Point(-PIXEL_EDGE * (np.sqrt(3) / 2), PIXEL_EDGE * .5)

        hexagon = MultiPoint([p1, p2, p3, p4, p5, p6]).convex_hull

        square_start = 186
        square_size = size
        square = Polygon([(-square_start, square_start), (-square_start + square_size, square_start),
                          (-square_start + square_size, square_start - square_size),
                          (-square_start, square_start - square_size),
                          (-square_start, square_start)])

        list_of_squares = [square]
        steps = int(np.ceil(np.abs(square_start * 2) / square_size))
        print(steps)

        pixel_index_to_grid = {}
        pix_index = 0
        # Generate tessellation of grid
        for x_step in range(steps):
            for y_step in range(steps):
                new_square = translate(square, xoff=x_step * square_size, yoff=-square_size * y_step)
                pixel_index_to_grid[pix_index] = [x_step, y_step]
                pix_index += 1
                list_of_squares.append(new_square)

        x, y = get_pixel_coords()
        list_hexagons = []
        for index, x_coor in enumerate(x):
            list_hexagons.append(translate(hexagon, x_coor, y[index]))
        list_pixels_and_fractions = {}
        for i in range(len(list_of_squares)):
            list_pixels_and_fractions[i] = []

        chid_to_pixel = {}
        for i in range(1440):
            chid_to_pixel[i] = []

        for pixel_index, pixel in enumerate(list_of_squares):
            for chid, hexagon in enumerate(list_hexagons):
                # Do the dirty work, hexagons should be in CHID order because translate in that order and append
                if pixel.intersects(hexagon):
                    intersection = pixel.intersection(hexagon)
                    fraction_whole = intersection.area / hexagon.area
                    if not np.isclose(fraction_whole, 0.0):
                        # so not close to zero overlap, add to list for that pixel
                        list_pixels_and_fractions[np.abs(pixel_index)].append((chid, fraction_whole))
                        chid_to_pixel[np.abs(1439 - chid)].append((pixel_index, fraction_whole))

        hex_to_grid = [chid_to_pixel, pixel_index_to_grid]
        return hex_to_grid

    def batch_processor(self):
        return NotImplemented

    def single_processor(self):
        return NotImplemented

    def reformat(self, image):
        dataset = np.swapaxes(image, 1, 3)
        dataset = np.array(dataset).reshape(self.shape).astype(np.float32)
        return dataset

    def format(self, batch):
        return NotImplemented

    def create_dataset(self):
        return NotImplemented