import math
from pathlib import Path
from typing import Union
from omegaconf import OmegaConf
from PIL import Image, ImageDraw

from data import read_frame_stats, FrameStats


class Grapher:
	def __init__(self, config: OmegaConf):
		self.image_height = 4
		self.output_dir = config.final_dir
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
		print(f'Creating graph image {file_path}')
		image = Image.new('RGB', (len(data_list), self.image_height))
		draw = ImageDraw.Draw(image)
		for x, each in enumerate(data_list):
			draw.line([(x, 0), (x, self.image_height)], fill=gradient(self.scale(each, lower_bound, upper_bound)))
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
			print(f'Could not read motion data for {name}. The file {bin_path} does not exist.')
			return None
		return read_frame_stats(bin_path)


	def scale(self, value, lower_bound, upper_bound):
		scaled = max(value - lower_bound, 1e-9) / (upper_bound - lower_bound)  # 1e-9 is to avoid log(0)
		return math.log1p(scaled * self.scale_boost) / math.log1p(self.scale_boost)


def make_gradient(stops, colours):
	"""
	stops: list of positions, must be 0..1
	colours: list of (r,g,b), must be same length as stops
	"""
	def gradient(t):
		t = max(0.0, min(1.0, t))
		for i in range(1, len(stops)):
			p0 = stops[i-1]
			c0 = colours[i-1]
			p1 = stops[i]
			c1 = colours[i]
			if t <= p1:
				f = (t - p0) / (p1 - p0) if p1 > p0 else 0
				return (
					int(c0[0] + (c1[0] - c0[0]) * f),
					int(c0[1] + (c1[1] - c0[1]) * f),
					int(c0[2] + (c1[2] - c0[2]) * f)
				)
		return colours[0]

	return gradient
