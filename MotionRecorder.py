# Taken from https://github.com/osmaa/pinymotion
import os
import io
import time
import queue
import threading
import logging

import picamera
from omegaconf import OmegaConf

from MotionVectorReader import MotionVectorReader


class MotionRecorder(threading.Thread):
	"""
	Record video into a circular memory buffer and extract motion vectors for simple motion detection analysis.
	Enables writing the video frames to file if motion is detected.
	"""

	_frames = 4 # number of frames which must contain movement to trigger

	_output = None


	def __init__(self, config: OmegaConf):
		super().__init__()
		self.camera = None
		self.stream = None
		self.motion = None
		self.width = config.width
		self.height = config.height
		self.sensor_mode = config.sensor_mode
		self.frame_rate = config.frame_rate
		self.bit_rate = config.bit_rate
		self.seconds_pre = config.seconds_pre   # Number of seconds to keep in buffer
		self.seconds_post = config.seconds_post # Number of seconds to record post end of motion
		self.file_pattern = '%y-%m-%dT%H-%M-%S' # Pattern for time.strfime


	def __enter__(self):
		self.start_camera()
		threading.Thread(name='annotate', target=self.annotate_with_datetime, args=(self.camera,), daemon=True).start()
		logging.info('Motion recorder ready')
		return self


	def __exit__(self, type, value, traceback):
		if self.camera.recording:
			self.camera.stop_recording()


	def wait(self, timeout = 0.0):
		"""Use this instead of time.sleep() from sub-threads so that they would wake up to exit quickly
		when instance is being shut down."""
		try:
			self.camera.wait_recording(timeout)
		except picamera.exc.PiCameraNotRecording:
			# that's fine, return immediately
			pass


	@property
	def frames(self):
		return self._frames


	@frames.setter
	def frames(self,value):
		self._frames=value
		if self.motion: self.motion.frames=value


	def start_camera(self):
		"""Sets up PiCamera to record H.264 High/4.1 profile video with enough
		intra frames that there is at least one in the in-memory circular buffer when
		motion is detected."""
		self.camera = picamera.PiCamera(clock_mode='raw', sensor_mode=self.sensor_mode,
		                                resolution=(self.width, self.height), framerate=self.frame_rate)
		self.stream = picamera.PiCameraCircularIO(self.camera, seconds=self.seconds_pre + 1, bitrate=self.bit_rate)
		self.motion = MotionVectorReader(self.camera, window=self.seconds_post * self.frame_rate, frames=self.frames)
		self.camera.start_recording(self.stream, motion_output=self.motion,
		                            format='h264', profile='high', level='4.1', bitrate=self.bit_rate,
		                            inline_headers=True, intra_period=self.seconds_pre * self.frame_rate // 2)
		self.camera.wait_recording(1)  # give camera some time to start up

	captures = queue.Queue()


	def run(self):
		"""Main loop of the motion recorder. Waits for trigger from the motion detector
		async task and writes in-memory circular buffer to file every time it happens,
		until motion detection trigger. After each recording, the name of the file
		is posted to captures queue, where whatever is consuming the recordings can
		pick it up.
		"""
		self.motion.disabled = False
		while self.camera.recording:
			# wait for motion detection
			if self.motion.wait(self.seconds_pre):
				if self.motion.has_detected_motion():
					try:
						# Start a new video, then append circular buffer to it until motion ends
						name = time.strftime(self.file_pattern)
						output = io.open(name + '.h264', 'wb')
						self.append_buffer(output, header=True)
						while self.motion.has_detected_motion() and self.camera.recording:
							self.wait(self.seconds_pre / 2)
							self.append_buffer(output)
					except picamera.PiCameraError as e:
						logging.error('Could not save recording: ' + e)
						pass
					finally:
						output.close()
						self._output = None
						self.captures.put(name)
					# Wait for the circular buffer to fill up before looping again
					self.wait(self.seconds_pre / 2)


	def append_buffer(self, output, header=False):
		"""Flush contents of circular framebuffer to current on-disk recording."""
		if header:
			header=picamera.PiVideoFrameType.sps_header
		else:
			header=None
		s = self.stream
		with s.lock:
			s.copy_to(output, seconds=self.seconds_pre, first_frame=header)
			s.clear()
		return output


	def annotate_with_datetime(self, camera):
		"""Background thread for annotating date and time to video."""
		while camera.recording:
			camera.annotate_text = time.strftime('%y-%m-%d %H:%M')
			camera.annotate_background = True
			self.wait(60-time.gmtime().tm_sec) # wait to beginning of minute

