# Taken from https://github.com/osmaa/pinymotion
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder
import webserver


try:
	config = OmegaConf.load('config.yaml')
	with MotionRecorder(config) as recorder:
		recorder.start()
		staging_dir = Path(config.staging_dir)
		final_dir = Path(config.final_dir)
		web_app = webserver.create(recorder.camera, final_dir)
		server_thread = webserver.run(web_app, host='0.0.0.0', port=config.web_port)
		while True:
			capture = recorder.captures.get()
			capture_info = capture[0]
			motion_stats = capture[1]
			print(f'Motion capture in "{capture_info.name}"')
			try:
				input_file = staging_dir.joinpath(f'{capture_info.name}.h264')
				output_file = final_dir.joinpath(f'{capture_info.name}.mp4')
				proc = subprocess.Popen(['./convert.sh', str(input_file), str(output_file), str(config.camera.frame_rate)])
				print(f'Starting conversion in sub process {proc.pid}')
			except Exception as e:
				print(f'Failed to convert video. {e}')

			json_path = final_dir.joinpath(f'{capture_info.name}.json')
			json_path.write_text(capture_info.t_json(), encoding='utf_8')
			#TODO:
			#  Create image file from statistics, height will be scaled to self.motion_upper_bound. Use logarithmic scaling
			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	exit()
