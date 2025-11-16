import math
from pathlib import Path
from PIL import Image, ImageDraw


class Grapher:
	def __init__(self, output_dir: Path, motion_threshold, motion_upper_bound):
		self.image_height = 4
		self.output_dir = output_dir
		self.motion_threshold = motion_threshold
		self.motion_upper_bound = motion_upper_bound

		# Start at black then transition through blue until `motion_threshold` where it goes
		# to yellow then slowly up to red at the maximum.
		below_threshold = (motion_threshold * 0.9) / motion_upper_bound
		threshold = motion_threshold / motion_upper_bound
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


	def make_image(self, name, graph_type, gradient, data_list, upper_bound):
		image = Image.new('RGB', (len(data_list), self.image_height))
		draw = ImageDraw.Draw(image)
		for x, each in enumerate(data_list):
			draw.line([(x, 0), (x, self.image_height)], fill=gradient(scale(each, upper_bound)))
		image.save(self.output_dir.joinpath(f'{name}-{graph_type}.png'))


	def make_motion_image(self, name, motion_list):
		self.make_image(name, 'motion', self.motion_gradient, motion_list, self.motion_upper_bound)


	def make_sad_image(self, name, sad_list):
		# Note: SAD value is normally a number much larger than 0, but occasionally it is 0.
		# Ignore these values so it doesn't affect the graph scaling.
		#TODO: Scale each value to that lowest becomes 0.
		self.make_image(name, 'sad', self.sad_gradient, sad_list, max(sad_list))



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


def scale(value, upper_bound):
	if value <= 0:
		return 0.0
	value = min(value, upper_bound)
	return math.log(value + 1) / math.log(upper_bound + 1)