# Taken from https://github.com/osmaa/pinymotion
import io
import time
import queue
import threading
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import picamerax as picamera
from omegaconf import OmegaConf

from MotionVectorReader import MotionVectorReader


#PiCamera settings that can be set from config file
allowed_camera_settings = [
	'awb_mode', 'brightness', 'contrast', 'saturation',
	'exposure_mode', 'exposure_compensation', 'iso', 'sharpness',
	'hflip', 'vflip', 'rotation', 'video_denoise', 'annotate_text_size'
]


@dataclass
class FrameStats:
	timestamp_utc: float
	motion_sum: int
	sad_sum: int


@dataclass
class CaptureInfo:
	name: str
	timestamp_utc: float
	length: int
	max_motion: int
	max_sad: int

	@classmethod
	def from_json(cls, s: str):
		return cls(**json.loads(s))

	def to_json(self) -> str:
		return json.dumps(asdict(self))


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
		self.config = config
		self.width = config.camera.width
		self.height = config.camera.height
		self.seconds_pre = config.seconds_pre    # Number of seconds to keep in buffer
		self.seconds_post = config.seconds_post  # Number of seconds to record post end of motion
		self.motion_threshold = config.motion_threshold     # Sum of all motion vectors should exceed this value
		self.motion_upper_bound = config.motion_upper_bound # This is the maximum we expect the sum to be
		self.file_pattern = '%Y-%m-%dT%H-%M-%S'  # Date pattern for saved recordings
		self.label_pattern = '%Y-%m-%d %H:%M'    # Date pattern for annotation text
		self.output_dir = Path(config.staging_dir)
		self.captures = queue.Queue()

		# Get time since boot. This is needed as the camera timestamps are relative to this.
		with open('/proc/uptime') as f:
			uptime_seconds = float(f.read().split()[0])
		now = datetime.now(timezone.utc)
		self.boot_timestamp_utc = (now - timedelta(seconds=uptime_seconds)).timestamp()


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
		camera_settings = self.config.camera
		self.camera = picamera.PiCamera(clock_mode='raw', sensor_mode=camera_settings.sensor_mode,
		                                resolution=(self.width, self.height), framerate=camera_settings.frame_rate)
		self.stream = picamera.PiCameraCircularIO(self.camera, seconds=self.seconds_pre + 1, bitrate=camera_settings.bit_rate)
		self.motion = MotionVectorReader(self.camera, motion_threshold=self.motion_threshold)
		self.camera.start_recording(self.stream, motion_output=self.motion,
		                            format='h264', profile='high', level='4.1', bitrate=camera_settings.bit_rate,
		                            intra_period=self.seconds_pre * camera_settings.frame_rate // 2)

		#TODO: Iterate over allowed_camera_settings and read these values from config dict
		self.camera.annotate_text_size = 15
		self.camera.hflip = camera_settings.hflip
		self.camera.vflip = camera_settings.vflip

		print('Waiting for camera to warm up...')
		self.camera.wait_recording(1)  # Give camera some time to start up
		self.motion.clear_trigger()    # then clear the triggered.
		self.motion.clear_statistics()


	def run(self):
		"""
		Main loop of the motion recorder. Waits for trigger from the motion detector async task
		and writes in-memory circular buffer to file every time it happens, until motion detection trigger.
		After each recording, info is posted to captures queue, where whatever is consuming the recordings
		can pick it up.
		"""
		while self.camera.recording:
			if self.motion.wait(self.seconds_pre):
				try:
					start_time = self.camera_time_to_wall_time(self.camera.timestamp) - self.seconds_pre
					self.motion.clear_trigger()
					name = time.strftime(self.file_pattern)
					# Start a new video, then append circular buffer to it until motion ends
					print('Started writing video file')
					with io.open(self.output_dir.joinpath(Path(name + '.h264')).absolute(), 'wb') as output:
						self.append_buffer(output, header=True)
						last_motion_time = time.monotonic()
						while self.camera.recording:
							if self.motion.has_detected_motion():
								self.motion.clear_trigger()
								last_motion_time = time.monotonic()
							self.wait(self.seconds_pre / 2)
							self.append_buffer(output)
							if time.monotonic() - last_motion_time > self.seconds_post:
								break
						end_time = self.camera_time_to_wall_time(self.camera.timestamp)
						motion_stats = self.convert_frame_times(self.motion.get_and_clear_statistics())
						max_motion = max(motion_stats, key=lambda each: each.motion_sum).motion_sum
						max_sad = max(motion_stats, key=lambda each: each.sad_sum).sad_sum
						self.captures.put(
							(CaptureInfo(name, start_time, end_time - start_time, max_motion, max_sad),
							 motion_stats)
						)
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


	def camera_time_to_wall_time(self, t):
		"""With clock_mode='raw' (see `start_camera`), timestamp is microseconds since system boot."""
		return self.boot_timestamp_utc + (t / 1000000)

	def convert_frame_times(self, frame_stats):
		return [
			FrameStats(self.camera_time_to_wall_time(fs.timestamp), fs.motion_sum, fs.sad_sum)
			for fs in frame_stats
		]