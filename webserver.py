import io
import threading
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import OrderedDict
from itertools import groupby
from omegaconf import OmegaConf
from picamerax import PiCamera
from picamerax.exc import PiCameraValueError
import flask
from flask import Flask, request, Response, url_for
from werkzeug.exceptions import BadRequest, NotFound

from data import CaptureInfo
from Grapher import Grapher
from MotionRecorder import get_camera_settings, apply_camera_settings


logger = logging.getLogger(__name__)

def create(camera, config: OmegaConf):
	logger.info('Setting up web server')

	log = logging.getLogger('werkzeug')
	log.setLevel(logging.ERROR)
	video_dir = config.video_dir
	frame_rate = config.camera.framerate
	grapher = Grapher(config)

	web_dir = str(Path(__file__).parent / 'web')
	app = Flask(__name__, static_folder=web_dir, template_folder=web_dir)

	def mjpeg_generator():
		"""Helper to produce MJPEG frames from the camera."""
		if camera is None:
			# No camera yet — yield a 1x1 black jpeg
			default = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + open('/dev/null','rb').read(0) + b'\r\n'
			logger.info('Sending blank preview')
			while True:
				yield default

		# Using a BytesIO and capture_continuous for MJPEG frames:
		stream = io.BytesIO()
		try:
			logger.info('Sending live preview')
			for _ in camera.capture_continuous(stream, format='jpeg', use_video_port=True):
				stream.seek(0)
				data = stream.read()
				if not data:
					continue
				yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n'
				stream.seek(0)
				stream.truncate()
		except GeneratorExit:
			# Flask will trigger this when the client disconnects
			logger.info('Client disconnected from live stream')
		except Exception as e:
			logger.error(f'Failed to provide MJPEG stream. {e}')
		finally:
			logger.info('Stopped sending preview')


	@app.route('/')
	def index():
		return flask.redirect(url_for('live'))


	@app.route('/live')
	def live():
		"""Live stream page"""
		return flask.render_template('live.html', awb_modes=PiCamera.AWB_MODES, exposure_modes=PiCamera.EXPOSURE_MODES)


	@app.route('/live/stream')
	def live_stream():
		"""Live MJPEG stream"""
		return Response(mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


	@app.route('/controls', methods=['GET', 'POST'])
	def camera_controls():
		if request.method == 'POST':
			try:
				apply_camera_settings(camera, request.get_json() or {})
			except (AttributeError, PiCameraValueError) as e:
				log_and_abort(BadRequest.code, str(e))
			return 'Ok'
		else:
			return get_camera_settings(camera, config.camera)


	@app.route('/captures')
	def captures():
		"""List files in the video directory"""
		items = []
		grouped = OrderedDict()
		if video_dir.exists():
			for path in sorted(video_dir.glob('*.mp4'), key=lambda x: x.stat().st_mtime, reverse=True):
				info = CaptureInfo.read_from_file(path.with_suffix('.json'))
				items.append({
					'name': info.name if info else path.stem,
					'timestamp': parse_time(info.start_time) if info else datetime.now(),
					'length': format_seconds(info.length_seconds) if info else '--',
					'max_motion': info.max_motion if info else '--',
					'max_sad': info.max_sad if info else '--'
				})
			for day, group in groupby(items, key=lambda each: each['timestamp'].date()):
				grouped[day] = list(group)

		return flask.render_template('captures.html', grouped=grouped)


	@app.route('/captures/download/<name>')
	def download_capture(name):
		"""Download the selected file"""
		return flask.send_from_directory(video_dir, name + '.mp4', as_attachment=False)


	@app.route('/captures/play/<name>')
	def play_capture(name):
		"""Play the selected file"""
		return flask.render_template('play.html', name=name, frame_rate=frame_rate)


	@app.route('/captures/graphs/<name>/max_motion')
	def max_motion_graph(name):
		return send_graph_image(grapher.get_max_motion_image(name))

	@app.route('/captures/graphs/<name>/motion_sum')
	def motion_sum_graph(name):
		return send_graph_image(grapher.get_motion_sum_image(name))

	@app.route('/captures/graphs/<name>/sad_sum')
	def sad_sum_graph(name):
		return send_graph_image(grapher.get_sad_sum_image(name))


	def send_graph_image(path: Path):
		if path is not None and path.exists():
			return flask.send_file(path, cache_timeout=timedelta(days=365).total_seconds())
		else:
			log_and_abort(NotFound.code, f'The file {path} does not exist')


	return app


def parse_time(t):
	return datetime.fromtimestamp(t / 1000000, tz=timezone.utc).astimezone()

def format_seconds(s):
	return f'{int(s/60):0d}m:{int(s%60):02d}s'

def log_and_abort(code, message):
	logger.warning(message)
	flask.abort(code, message)


def run(app, host, port):
	logger.info('Starting web server...')
	server = threading.Thread(target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False), daemon=True)
	server.start()
	logger.info(f'Web server is running on port {port}')
	return server