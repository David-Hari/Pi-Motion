# Taken from https://github.com/osmaa/pinymotion
import threading
from collections import deque
from dataclasses import dataclass
import picamerax as picamera
import picamerax.array
import numpy as np
from omegaconf import OmegaConf

from data import FrameStats


class MotionVectorReader(picamera.array.PiMotionAnalysis):
	"""
	This is a hardware-assisted motion detector using H.264 motion vector data.
	The Pi camera outputs 16x16 macro block MVs, so we only have about 5000 blocks per frame to process.
	Numpy is fast enough for that.
	"""

	def __init__(self, camera, boot_timestamp, pre_frames, config: OmegaConf):
		"""Initialize motion vector reader"""
		super(type(self), self).__init__(camera)
		self.camera = camera
		self.boot_timestamp = boot_timestamp   # Needed to calculate absolute time of each frame
		self.per_block_threshold = config.per_block_threshold
		self.num_threshold_blocks = config.num_threshold_blocks
		self.per_frame_threshold = config.per_frame_threshold
		self.trigger = threading.Event()
		self.pre_record_statistics = deque(maxlen=pre_frames)
		self.statistics = []
		self.stats_lock = threading.Lock()
		self.is_recording = False


	def has_detected_motion(self):
		return self.trigger.is_set()


	def wait(self, timeout=0.0):
		return self.trigger.wait(timeout)


	def clear_trigger(self):
		self.trigger.clear()

	def start_capturing_statistics(self):
		with self.stats_lock:
			self.is_recording = True
			self.statistics = list(self.pre_record_statistics)

	def stop_capturing_and_get_stats(self):
		with self.stats_lock:
			self.is_recording = False
			s = self.statistics.copy()
			self.pre_record_statistics.clear()
			self.statistics.clear()
			return s


	def clear_statistics(self):
		with self.stats_lock:
			self.pre_record_statistics.clear()
			self.statistics.clear()


	# from profilehooks import profile
	# @profile
	def analyze(self, data):
		"""
		Runs once per frame on a 16x16 motion vector block buffer (about 5000 values).
		Must be faster than frame rate (e.g. max 100 ms for 10 fps stream).
		Sets `self.trigger` event to trigger capture.
		"""

		frame_time = self.camera.frame.timestamp
		if frame_time is None:   # PiCamera documentation says timestamp can occasionally be "unknown"
			return

		# Get direction vector
		direction = np.sqrt(
			np.square(data['x'].astype(np.float)) +
			np.square(data['y'].astype(np.float))
		)

		max_direction = int(direction.max())
		num_over_threshold = (direction > self.per_block_threshold).sum()
		direction_sum = int(direction.sum())
		sad_sum = int(data['sad'].sum())

		with self.stats_lock:
			stats = FrameStats(self.boot_timestamp + frame_time, max_direction, direction_sum, sad_sum)
			if self.is_recording:
				self.statistics.append(stats)
			else:
				self.pre_record_statistics.append(stats)

		if num_over_threshold > self.num_threshold_blocks or direction_sum > self.per_frame_threshold:
			self.trigger.set()
