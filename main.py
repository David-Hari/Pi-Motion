# Taken from https://github.com/osmaa/pinymotion

import logging
from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder


logging.basicConfig(filename='log.txt', level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
try:
	with MotionRecorder(OmegaConf.load('config.yaml')) as recorder:
		recorder.start()
		while True:
			recording = recorder.captures.get()
			# TODO: Put this in script
			# Wrap h264 in mkv container with appropriate fps
			#os.system(f'ffmpeg -r {str(self.frame_rate)} -i {path} -vcodec copy {mkvpath} >/dev/null 2>&1')
			#os.remove(path)  # Delete original .h264 file
			logging.info('Motion capture in "{0}"'.format(recording))
			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	exit()
