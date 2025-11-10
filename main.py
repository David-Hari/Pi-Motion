# Taken from https://github.com/osmaa/pinymotion

from omegaconf import OmegaConf

from MotionRecorder import MotionRecorder


try:
	with MotionRecorder(OmegaConf.load('config.yaml')) as recorder:
		recorder.start()
		while True:
			recording = recorder.captures.get()
			# TODO: Pass arguments, and don't wait
			#os.system('./convert.sh')
			print(f'Motion capture in "{recording}"')
			recorder.captures.task_done()
except (KeyboardInterrupt, SystemExit):
	exit()
