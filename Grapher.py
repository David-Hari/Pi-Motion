import math
import logging
from pathlib import Path
from typing import Union
from omegaconf import OmegaConf
import numpy as np
from PIL import Image

from data import read_frame_stats, FrameStats


logger = logging.getLogger(__name__)

class Grapher:
	def __init__(self, config: OmegaConf):
		self.image_height = 4
		self.output_dir = config.data_dir
		self.per_block_threshold = config.per_block_threshold
		self.per_frame_threshold = config.per_frame_threshold
		self.per_block_upper_bound = config.per_block_upper_bound
		self.per_frame_upper_bound = config.per_frame_upper_bound
		self.scale_boost = config.scale_boost

		# Start at black then transition through blue until the threshold where it goes
		# to yellow then slowly up to red at the maximum.
		gradient_colours = [ (0, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 0) ]

		below_threshold = self.scale(self.per_block_threshold * 0.9, 0, self.per_block_upper_bound)
		threshold = self.scale(self.per_block_threshold, 0, self.per_block_upper_bound)
		self.max_motion_gradient = make_gradient([ 0.0, below_threshold, threshold, 1.0 ], gradient_colours)

		below_threshold = self.scale(self.per_frame_threshold * 0.9, 0, self.per_frame_upper_bound)
		threshold = self.scale(self.per_frame_threshold, 0, self.per_frame_upper_bound)
		self.motion_sum_gradient = make_gradient([ 0.0, below_threshold, threshold, 1.0 ], gradient_colours)

		# S.A.D is scaled dynamically based on max value per video, so instead of a threshold with transitioning
		# colours, just go from one colour to another.
		self.sad_gradient = make_gradient([ 0.0, 1.0 ], [ (0, 0, 0), (255, 255, 0) ])


	def make_image(self, file_path: Path, gradient, data_list, lower_bound, upper_bound):
		logger.info(f'Creating graph image {file_path}')
		values = np.asarray(data_list, dtype=np.float32)
		colors = gradient(self.scale(values, lower_bound, upper_bound))  # (N, 3) array
		img_data = np.repeat(colors[np.newaxis, :, :], self.image_height, axis=0)
		image = Image.fromarray(img_data, mode='RGB')
		image.save(file_path)


	def get_max_motion_image(self, name) -> Path:
		image_path = self.output_dir.joinpath(f'{name}-max-motion.png')
		stats = self.read_stats_if_needed(image_path, name)
		if stats is not None:
			motion_list = [each.max_motion for each in stats]
			self.make_image(image_path, self.max_motion_gradient, motion_list, 0, self.per_block_upper_bound)
		return image_path


	def get_motion_sum_image(self, name) -> Path:
		image_path = self.output_dir.joinpath(f'{name}-motion-sum.png')
		stats = self.read_stats_if_needed(image_path, name)
		if stats is not None:
			motion_list = [each.motion_sum for each in stats]
			self.make_image(image_path, self.motion_sum_gradient, motion_list, 0, self.per_frame_upper_bound)
		return image_path


	def get_sad_sum_image(self, name) -> Path:
		image_path = self.output_dir.joinpath(f'{name}-sad-sum.png')
		stats = self.read_stats_if_needed(image_path, name)
		if stats is not None:
			sad_list = [each.sad_sum for each in stats]
			# Note: SAD value is normally a number much larger than 0, but occasionally it is 0.
			# So that it doesn't affect the graph scaling, change any small values to be equal to a neighbouring value.
			for i in range(1, len(sad_list)):
				if sad_list[i] < 10:
					sad_list[i] = sad_list[i-1]
			self.make_image(image_path, self.sad_gradient, sad_list, min(sad_list), max(sad_list))
		return image_path


	def read_stats_if_needed(self, image_path: Path, name: str) -> Union[list[FrameStats], None]:
		if image_path.exists():
			return None
		bin_path = self.output_dir.joinpath(f'{name}.bin')
		if not bin_path.exists():
			logger.error(f'Could not read motion data for {name}. The file {bin_path} does not exist.')
			return None
		return read_frame_stats(bin_path)


	def scale(self, value, lower_bound, upper_bound):
		# value may be scalar or NumPy array
		value = np.asarray(value, dtype=np.float32)
		scaled = np.maximum(value - lower_bound, 1e-9) / (upper_bound - lower_bound)  # 1e-9 is to avoid log(0)
		return np.log1p(scaled * self.scale_boost) / math.log1p(self.scale_boost)


def make_gradient(stops, colours):
	"""
	stops: list of positions, must be 0..1
	colours: list of (r,g,b), must be same length as stops
	"""
	stops = np.asarray(stops, dtype=np.float32)
	colours = np.asarray(colours, dtype=np.float32)

	def gradient(t):
		t = np.asarray(t, dtype=np.float32)
		t = np.clip(t, 0.0, 1.0)

		# For each t, find the segment (p0,p1)
		indices = np.searchsorted(stops, t, side='right') - 1
		indices = np.clip(indices, 0, len(stops) - 2)

		p0 = stops[indices]
		p1 = stops[indices + 1]
		c0 = colours[indices]
		c1 = colours[indices + 1]

		f = (t - p0) / (p1 - p0)
		f = f[:, None]  # Broadcast into RGB shape

		return (c0 + (c1 - c0) * f).astype(np.uint8)

	return gradient
