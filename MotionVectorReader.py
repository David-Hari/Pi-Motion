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

	frames = 0
	window = 0
	camera = None
	trigger = threading.Event()
	output = None


	def __init__(self, camera, window=10, frames=4):
		"""Initialize motion vector reader"""
		super(type(self), self).__init__(camera)
		self.camera = camera
		self.frames = frames
		self.window = window
		self.previous_frames = deque(maxlen=window)


	def save_motion_vectors(self, file):
		self.output = open(file, 'ab')


	def has_detected_motion(self):
		return self.trigger.is_set()


	def wait(self, timeout=0.0):
		return self.trigger.wait(timeout)

	disabled = False
	noise = None


	# from profilehooks import profile
	# @profile
	def analyze(self, data):
		"""Runs once per frame on a 16x16 motion vector block buffer (about 5000 values).
		Must be faster than frame rate (max 100 ms for 10 fps stream).
		Sets self.trigger Event to trigger capture.
		"""

		if self.disabled:
			self.previous_frames.append(False)
			return

		import struct
		if self.output:
			self.output.write(struct.pack('>8sL?8sBBB',
			                              b'frameno\x00', self.camera.frame.index, self.has_detected_motion(),
			                              b'mvarray\x00', data.shape[0], data.shape[1], data[0].itemsize))
			self.output.write(data)

		# The motion vector array we get from the camera contains three values per
		# macroblock: the X and Y components of the inter-block motion vector, and
		# sum-of-differences value. The SAD value has a completely different meaning
		# on a per-frame basis, but abstracted over a longer timeframe in a mostly-still
		# video stream, it ends up estimating noise pretty well. Accordingly, we
		# can use it in a decay function to reduce sensitivity to noise on a per-block
		# basis

		# Accumulate and decay SAD field
		noise = self.noise
		if not noise:
			noise = np.zeros(data.shape, dtype=np.short)
		shift = max(self.window.bit_length() - 2, 0)
		noise -= (noise >> shift) + 1  # decay old noise
		noise = np.add(noise, data['sad'] >> shift).clip(0)

		# Get direction vector
		direction = np.sqrt(
			np.square(data['x'].astype(np.float)) +
			np.square(data['y'].astype(np.float))
		).clip(0, 255).astype(np.uint8)

		# Look for the largest continuous area in picture that has motion
		mask = (direction > (noise >> 4))   # Every motion vector exceeding current noise field
		#TODO: What does this do?  labels,count = ndimage.label(mask) # label all motion areas
		#sizes = ndimage.sum(mask, labels, range(count + 1)) # number of MV blocks per area
		#largest = np.sort(sizes)[-1] # what's the size of the largest area

		# Does that area size exceed the minimum motion threshold?
		#motion = (largest >= self.area)

		# Then consider motion repetition
		#self.previous_frames.append(motion)

		def count_longest(a, value):
			ret = i = 0
			while i < len(a):
				for j in range(0, len(a) - i):
					if a[i + j] != value: break
					ret = max(ret, j + 1)
				i += j + 1
			return ret

		longest_motion_sequence = count_longest(self.previous_frames, True)

		if longest_motion_sequence >= self.frames:
			self.trigger.set()
		elif longest_motion_sequence < 1:
			# clear motion flag once motion has ceased entirely
			self.trigger.clear()
