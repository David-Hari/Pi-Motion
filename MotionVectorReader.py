# Taken from https://github.com/osmaa/pinymotion
import threading
from collections import deque
import picamerax as picamera
import picamerax.array
import numpy as np


class MotionVectorReader(picamera.array.PiMotionAnalysis):
	"""
	This is a hardware-assisted motion detector using H.264 motion vector data.
	The Pi camera outputs 16x16 macro block MVs, so we only have about 5000 blocks per frame to process.
	Numpy is fast enough for that.
	"""

	window = 0
	output = None


	def __init__(self, camera, window, motion_threshold):
		"""Initialize motion vector reader"""
		super(type(self), self).__init__(camera)
		self.camera = camera
		self.window = window
		self.motion_threshold = motion_threshold
		self.previous_frames = deque(maxlen=window)
		self.trigger = threading.Event()


	def save_motion_vectors(self, file):
		self.output = open(file, 'ab')


	def has_detected_motion(self):
		return self.trigger.is_set()


	def wait(self, timeout=0.0):
		return self.trigger.wait(timeout)


	# from profilehooks import profile
	# @profile
	def analyze(self, data):
		"""Runs once per frame on a 16x16 motion vector block buffer (about 5000 values).
		Must be faster than frame rate (max 100 ms for 10 fps stream).
		Sets `self.trigger` Event to trigger capture.
		"""

		import struct
		if self.output:
			self.output.write(struct.pack('>8sL?8sBBB',
			                              b'frameno\x00', self.camera.frame.index, self.has_detected_motion(),
			                              b'mvarray\x00', data.shape[0], data.shape[1], data[0].itemsize))
			self.output.write(data)

		# Get direction vector
		direction = np.sqrt(
			np.square(data['x'].astype(np.float)) +
			np.square(data['y'].astype(np.float))
		).clip(0, 255).astype(np.uint8)

		direction_sum = direction.sum()
		sad_sum = data['sad'].sum()
		#TODO: Store these in arrays that can be accessed later to generate a graph or something

		if direction_sum > self.motion_threshold:
			self.trigger.set()
		else:
			self.trigger.clear()
