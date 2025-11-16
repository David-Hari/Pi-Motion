import math
from pathlib import Path
from omegaconf import OmegaConf
from PIL import Image, ImageDraw


class Grapher:
	def __init__(self, output_dir: Path, config: OmegaConf):
		self.image_height = 4
		self.output_dir = output_dir
		self.motion_threshold = config.motion_threshold
		self.motion_upper_bound = config.motion_upper_bound
		self.scale_boost = config.scale_boost

		# Start at black then transition through blue until `motion_threshold` where it goes
		# to yellow then slowly up to red at the maximum.
		below_threshold = self.scale(self.motion_threshold * 0.9, 0, self.motion_upper_bound)
		threshold = self.scale(self.motion_threshold, 0, self.motion_upper_bound)
		self.motion_gradient = make_gradient([
			(0.0, (0, 0, 0)),
			(below_threshold, (0, 0, 128)),
			(threshold, (255, 255, 0)),
			(1.0, (255, 0, 0))
		])

		# Similar to above but there is no threshold
		self.sad_gradient = make_gradient([
			(0.0, (0, 0, 0)),
			(0.3, (0, 0, 128)),
			(0.4, (255, 255, 0)),
			(1.0, (255, 0, 0))
		])


	def make_image(self, name, graph_type, gradient, data_list, lower_bound, upper_bound):
		image = Image.new('RGB', (len(data_list), self.image_height))
		draw = ImageDraw.Draw(image)
		for x, each in enumerate(data_list):
			draw.line([(x, 0), (x, self.image_height)], fill=gradient(self.scale(each, lower_bound, upper_bound)))
		image.save(self.output_dir.joinpath(f'{name}-{graph_type}.png'))


	def make_motion_image(self, name, motion_list):
		self.make_image(name, 'motion', self.motion_gradient, motion_list, 0, self.motion_upper_bound)


	def make_sad_image(self, name, sad_list):
		# Note: SAD value is normally a number much larger than 0, but occasionally it is 0.
		# Ignore these values so that it doesn't affect the graph scaling.
		nonzero = [x for x in sad_list if x > 0]
		self.make_image(name, 'sad', self.sad_gradient, sad_list, min(nonzero), max(sad_list))


	def scale(self, value, lower_bound, upper_bound):
		scaled = max(value - lower_bound, 1e-9) / (upper_bound - lower_bound)  # 1e-9 is to avoid log(0)
		return math.log1p(scaled * self.scale_boost) / math.log1p(self.scale_boost)


def make_gradient(stops):
	"""
	stops: list of (position, (r,g,b)). position must be 0..1
	"""
	stops = sorted(stops, key=lambda s: s[0])

	def gradient(t):
		t = max(0.0, min(1.0, t))
		for i in range(1, len(stops)):
			p0, c0 = stops[i-1]
			p1, c1 = stops[i]
			if t <= p1:
				f = (t - p0) / (p1 - p0) if p1 > p0 else 0
				return (
					int(c0[0] + (c1[0] - c0[0]) * f),
					int(c0[1] + (c1[1] - c0[1]) * f),
					int(c0[2] + (c1[2] - c0[2]) * f)
				)
		return stops[-1][1]

	return gradient
