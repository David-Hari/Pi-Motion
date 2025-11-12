# Taken from https://github.com/osmaa/pinymotion
import subprocess
from pathlib import Path
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder


try:
	config = OmegaConf.load('config.yaml')
	with MotionRecorder(config) as recorder:
		recorder.start()
		while True:
			file_name = recorder.captures.get()
			print(f'Motion capture in "{file_name}"')
			try:
				input_file = Path(config.staging_dir, file_name + '.h264')
				output_file = Path(config.final_dir, file_name + '.mkv')
				proc = subprocess.Popen(['./convert.sh', str(input_file), str(output_file), str(config.frame_rate)])
				print(f'Starting conversion in sub process {proc.pid}')
			except Exception as e:
				print(f'Failed to convert video. {e}')
			# TODO: Maybe background thread to take motion data from reader and create image.
			#  Or have it done in MotionRecorder
			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	exit()
