# Taken from https://github.com/osmaa/pinymotion
import subprocess
from pathlib import Path
from dataclasses import dataclass
from omegaconf import OmegaConf, MISSING
from typing import Optional

from MotionRecorder import MotionRecorder
from data import write_frame_stats
import webserver


@dataclass
class CameraConfig:
	""" These properties are identical to those available on the picamera.PiCamera class """
	width: int = MISSING
	height: int = MISSING
	framerate: int = 15
	bitrate: int = 2000000   # 2Mbps is a high quality stream for 10 fps HD video
	sensor_mode: Optional[int] = 0
	awb_mode: Optional[str] = None         # See PiCamera.AWB_MODES
	brightness: Optional[int] = None       # 0 to 100
	contrast: Optional[int] = None         # -100 to 100
	saturation: Optional[int] = None       # -100 to 100
	exposure_mode: Optional[str] = None    # See PiCamera.EXPOSURE_MODES
	exposure_compensation: Optional[int] = None # -25 to 25
	iso: Optional[int] = None
	sharpness: Optional[int] = None        # -100 and 100
	hflip: Optional[bool] = None
	vflip: Optional[bool] = None
	rotation: Optional[int] = None         # One of 0, 90, 180, and 270
	video_denoise: Optional[bool] = None
	annotate_text_size: Optional[int] = 15 # 6 to 160


@dataclass
class AppConfig:
	camera: CameraConfig
	staging_dir: Path
	# TODO: Maybe insted have video_dir for mp4 files and data_dir for json, bin and png. data_dir can default to video_dir
	final_dir: Path
	seconds_pre: int = 10
	seconds_post: int = 60
	per_block_threshold: int = 50   # Motion vector for a single block in a frame must equal or exceed this value
	num_threshold_blocks: int = 10  # Number of motion vector blocks to have met the `per_block_threshold`
	per_frame_threshold: int = 1500 # Sum of all motion vectors in a frame must equal or exceed this value
	per_block_upper_bound: int = 100   # This is the highest we expect the motion vector per block to be. Used for graph scaling.
	per_frame_upper_bound: int = 50000 # This is the highest we expect the sum of all vectors per frame to be. Used for graph scaling.
	scale_boost: int = 20           # How much to boost lower values in log-scaled graphs. 5 = mild, 10 = medium, 50 = strong, 100 = very strong
	web_port: int = 8080


schema = OmegaConf.structured(AppConfig)
config = OmegaConf.merge(schema, OmegaConf.load('config.yaml'))
try:
	with MotionRecorder(config) as recorder:
		recorder.start()
		web_app = webserver.create(recorder.camera, config)
		webserver.run(web_app, host='0.0.0.0', port=config.web_port)
		while True:
			capture = recorder.captures.get()
			capture_info = capture[0]
			frame_stats = capture[1]
			print(f'Motion capture in "{capture_info.name}"')

			# Convert file
			try:
				input_file = config.staging_dir.joinpath(f'{capture_info.name}.h264')
				output_file = config.final_dir.joinpath(f'{capture_info.name}.mp4')
				proc = subprocess.Popen(['./convert.sh', str(input_file), str(output_file), str(config.camera.framerate)])
				print(f'Starting conversion in sub process {proc.pid}')
			except Exception as e:
				print(f'Failed to convert video. {e}')

			capture_info.write_to_file(config.final_dir)
			write_frame_stats(config.final_dir, capture_info.name, frame_stats)

			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	print('Shutting down')
	exit()
