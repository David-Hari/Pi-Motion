# Taken from https://github.com/osmaa/pinymotion
import subprocess
from pathlib import Path
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder
import webserver


def run():
	try:
		config = OmegaConf.load('config.yaml')
		with MotionRecorder(config) as recorder:
			recorder.start()
			staging_dir = Path(config.staging_dir)
			final_dir = Path(config.final_dir)
			web_app = webserver.create(recorder.camera, final_dir)
			webserver.run(web_app, host='0.0.0.0', port=config.web_port)
			while True:
				capture = recorder.captures.get()
				capture_info = capture[0]
				motion_stats = capture[1]
				print(f'Motion capture in "{capture_info.name}"')
				#print(f'# {datetime.fromtimestamp(capture_info.timestamp_utc, tz=timezone.utc)}\t{capture_info.length_seconds}\t{capture_info.max_motion}\t{capture_info.max_sad}')
				#print(f'- {datetime.fromtimestamp(motion_stats[0].timestamp_utc, tz=timezone.utc)}')
				#print(f'- {datetime.fromtimestamp(motion_stats[len(motion_stats)-1].timestamp_utc, tz=timezone.utc)}')
				try:
					input_file = staging_dir.joinpath(f'{capture_info.name}.h264')
					output_file = final_dir.joinpath(f'{capture_info.name}.mp4')
					proc = subprocess.Popen(['./convert.sh', str(input_file), str(output_file), str(config.camera.frame_rate)])
					print(f'Starting conversion in sub process {proc.pid}')
				except Exception as e:
					print(f'Failed to convert video. {e}')

				write_json_file(final_dir, capture_info)
				make_graph_image(final_dir, motion_stats)
				recorder.captures.task_done()
	except (KeyboardInterrupt, SystemExit):
		print('Shutting down')
		exit()


def write_json_file(output_dir, capture_info):
	json_path = output_dir.joinpath(f'{capture_info.name}.json')
	json_path.write_text(capture_info.to_json(), encoding='utf_8')


def make_graph_image(output_dir, capture_info):
	#TODO:
	#  Create image file from statistics, height will be scaled to self.motion_upper_bound. Use logarithmic scaling
	pass


if __name__ == '__main__':
	run()