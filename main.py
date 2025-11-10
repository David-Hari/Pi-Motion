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
			# TODO: Pass arguments, and don't wait
			#os.system('./convert.sh')
			logging.info('Motion capture in "{0}"'.format(recording))
			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	exit()
