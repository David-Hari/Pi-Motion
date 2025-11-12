# Taken from https://github.com/osmaa/pinymotion
import io
import time
import queue
import threading
from pathlib import Path
import picamerax as picamera
from omegaconf import OmegaConf

from MotionVectorReader import MotionVectorReader


class MotionRecorder(threading.Thread):
	"""
	Record video into a circular memory buffer and extract motion vectors for simple motion detection analysis.
	Enables writing the video frames to file if motion is detected.
	"""

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
		self.seconds_pre = config.seconds_pre    # Number of seconds to keep in buffer
		self.seconds_post = config.seconds_post  # Number of seconds to record post end of motion
		self.motion_threshold = config.motion_threshold  # Sum of all motion vectors should exceed this value
		self.file_pattern = '%Y-%m-%dT%H-%M-%S'  # Date pattern for saved recordings
		self.label_pattern = '%Y-%m-%d %H:%M'    # Date pattern for annotation text
		self.output_dir = Path(config.staging_dir)
		self.captures = queue.Queue()


	def __enter__(self):
		self.start_camera()
		threading.Thread(name='annotate', target=self.annotate_with_datetime, args=(self.camera,), daemon=True).start()
		print('Motion recorder ready')
		return self


	def __exit__(self, type, value, traceback):
		if self.camera.recording:
			self.camera.stop_recording()


	def wait(self, timeout=0.0):
		"""Use this instead of time.sleep() from sub-threads so that they would wake up to exit quickly
		when instance is being shut down."""
		try:
			self.camera.wait_recording(timeout)
		except picamera.exc.PiCameraNotRecording:
			# that's fine, return immediately
			pass


	def start_camera(self):
		"""Sets up PiCamera to record H.264 High/4.1 profile video with enough
		intra frames that there is at least one in the in-memory circular buffer when
		motion is detected."""
		print('Starting camera')
		self.camera = picamera.PiCamera(clock_mode='raw', sensor_mode=self.sensor_mode,
		                                resolution=(self.width, self.height), framerate=self.frame_rate)
		self.stream = picamera.PiCameraCircularIO(self.camera, seconds=self.seconds_pre + 1, bitrate=self.bit_rate)
		self.motion = MotionVectorReader(self.camera, window=self.seconds_post * self.frame_rate, motion_threshold=self.motion_threshold)
		self.camera.start_recording(self.stream, motion_output=self.motion,
		                            format='h264', profile='high', level='4.1', bitrate=self.bit_rate,
		                            intra_period=self.seconds_pre * self.frame_rate // 2)
		self.camera.annotate_text_size = 15
		print('Waiting for camera to warm up...')
		self.camera.wait_recording(1)  # give camera some time to start up


	def run(self):
		"""Main loop of the motion recorder. Waits for trigger from the motion detector
		async task and writes in-memory circular buffer to file every time it happens,
		until motion detection trigger. After each recording, the name of the file
		is posted to captures queue, where whatever is consuming the recordings can
		pick it up.
		"""
		while self.camera.recording:
			print('# 1')
			if self.motion.wait(self.seconds_pre):
				print('# 2')
				try:
					# Start a new video, then append circular buffer to it until motion ends
					self.motion.clear_trigger()
					name = time.strftime(self.file_pattern)
					print('Started writing video file')
					with io.open(self.output_dir.joinpath(Path(name + '.h264')).absolute(), 'wb') as output:
						print('# 3')
						self.append_buffer(output, header=True)
						print('# 4')
						last_motion_time = time.monotonic()
						while self.camera.recording:
							print('# 5')
							if self.motion.has_detected_motion():
								#TODO: This only checks if motion is happening right now.
								print('# motion')
								self.motion.clear_trigger()
								last_motion_time = time.monotonic()
							self.wait(self.seconds_pre / 2)
							print('# 6')
							self.append_buffer(output)
							print('# 7')
							if time.monotonic() - last_motion_time > self.seconds_post:
								break
						self.captures.put(name)
					print('Finished writing video file')
				except picamera.PiCameraError as e:
					print('Could not save recording: ' + e)
					pass
				# Wait for the circular buffer to fill up before looping again
				self.wait(self.seconds_pre / 2)


	def append_buffer(self, output, header=False):
		"""Flush contents of circular framebuffer to current on-disk recording."""
		s = self.stream
		with s.lock:
			s.copy_to(output, seconds=self.seconds_pre, first_frame=picamera.PiVideoFrameType.sps_header if header else None)
			s.clear()
		return output


	def annotate_with_datetime(self, camera):
		"""Background thread for annotating date and time to video."""
		while camera.recording:
			camera.annotate_text = time.strftime(self.label_pattern)
			self.wait(60-time.gmtime().tm_sec) # wait to beginning of minute

