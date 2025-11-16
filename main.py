# Taken from https://github.com/osmaa/pinymotion
import subprocess
from pathlib import Path
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder
import webserver
from Grapher import Grapher


try:
	config = OmegaConf.load('config.yaml')
	staging_dir = Path(config.staging_dir)
	final_dir = Path(config.final_dir)
	g = Grapher(final_dir, config.motion_threshold, config.motion_upper_bound)
	with MotionRecorder(config) as recorder:
		recorder.start()
		web_app = webserver.create(recorder.camera, final_dir)
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

			# Write info to JSON file
			json_path = final_dir.joinpath(f'{capture_info.name}.json')
			json_path.write_text(capture_info.to_json(), encoding='utf_8')

			# Create motion graph images
			g.make_motion_image(capture_info.name, [each.motion_sum for each in motion_stats])
			g.make_sad_image(capture_info.name, [each.sad_sum for each in motion_stats])

			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	print('Shutting down')
	exit()
