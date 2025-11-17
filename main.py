# Taken from https://github.com/osmaa/pinymotion
import subprocess
from pathlib import Path
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder, write_capture_info, write_motion_stats
import webserver


#PiCamera settings that can be set from config file
allowed_camera_settings = [
	'awb_mode', 'brightness', 'contrast', 'saturation',
	'exposure_mode', 'exposure_compensation', 'iso', 'sharpness',
	'hflip', 'vflip', 'rotation', 'video_denoise', 'annotate_text_size'
]
#TODO:
# Somehow make OmegaConf aware of the above as camera.xxx
# Make dirs in config Path objects
# Give defaults to settings and maybe min/max

try:
	config = OmegaConf.load('config.yaml')
	staging_dir = Path(config.staging_dir)
	final_dir = Path(config.final_dir)
	with MotionRecorder(config) as recorder:
		recorder.start()
		web_app = webserver.create(recorder.camera, config)
		webserver.run(web_app, host='0.0.0.0', port=config.web_port)
		while True:
			capture = recorder.captures.get()
			capture_info = capture[0]
			motion_stats = capture[1]
			print(f'Motion capture in "{capture_info.name}"')

			# Convert file
			try:
				input_file = staging_dir.joinpath(f'{capture_info.name}.h264')
				output_file = final_dir.joinpath(f'{capture_info.name}.mp4')
				proc = subprocess.Popen(['./convert.sh', str(input_file), str(output_file), str(config.camera.frame_rate)])
				print(f'Starting conversion in sub process {proc.pid}')
			except Exception as e:
				print(f'Failed to convert video. {e}')

			write_capture_info(final_dir, capture_info.name, capture_info)
			write_motion_stats(final_dir, capture_info.name, motion_stats)

			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	print('Shutting down')
	exit()
