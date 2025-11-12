# Taken from https://github.com/osmaa/pinymotion
import threading
import picamerax as picamera
import picamerax.array
import numpy as np


class MotionVectorReader(picamera.array.PiMotionAnalysis):
	"""
	This is a hardware-assisted motion detector using H.264 motion vector data.
	The Pi camera outputs 16x16 macro block MVs, so we only have about 5000 blocks per frame to process.
	Numpy is fast enough for that.
	"""

	def __init__(self, camera, motion_threshold):
		"""Initialize motion vector reader"""
		super(type(self), self).__init__(camera)
		self.camera = camera
		self.motion_threshold = motion_threshold
		self.trigger = threading.Event()


	def has_detected_motion(self):
		return self.trigger.is_set()


	def clear_trigger(self):
		self.trigger.clear()


	def wait(self, timeout=0.0):
		return self.trigger.wait(timeout)


	# from profilehooks import profile
	# @profile
	def analyze(self, data):
		"""Runs once per frame on a 16x16 motion vector block buffer (about 5000 values).
		Must be faster than frame rate (max 100 ms for 10 fps stream).
		Sets `self.trigger` Event to trigger capture.
		"""

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
