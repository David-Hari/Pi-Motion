import io
import threading
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from omegaconf import OmegaConf
import flask
from flask import Flask, Response, url_for

from MotionRecorder import read_capture_info
from Grapher import Grapher


def create(camera, config: OmegaConf):
	print('Setting up web server')

	log = logging.getLogger('werkzeug')
	log.setLevel(logging.ERROR)
	video_dir = Path(config.final_dir)
	grapher = Grapher(config)

	web_dir = str(Path(__file__).parent / 'web')
	app = Flask(__name__, static_folder=web_dir, template_folder=web_dir)

	def mjpeg_generator():
		"""Helper to produce MJPEG frames from the camera."""
		if camera is None:
			# No camera yet — yield a 1x1 black jpeg
			default = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + open('/dev/null','rb').read(0) + b'\r\n'
			print('Sending blank preview')
			while True:
				yield default

		# Using a BytesIO and capture_continuous for MJPEG frames:
		stream = io.BytesIO()
		try:
			print('Sending live preview')
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
			print('Client disconnected from live stream')
		except Exception as e:
			print(f'Failed to provide MJPEG stream. {e}')
		finally:
			print('Stopped sending preview')


	@app.route('/')
	def index():
		return flask.redirect(url_for('live'))


	@app.route('/live')
	def live():
		"""Live stream page"""
		return flask.render_template('live.html')


	@app.route('/live/stream')
	def live_stream():
		"""Live MJPEG stream"""
		return Response(mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


	@app.route('/captures')
	def captures():
		"""List files in the video directory"""
		items = []
		if video_dir.exists():
			for path in sorted(video_dir.glob('*.mp4'), key=lambda x: x.stat().st_mtime):
				info = read_capture_info(path.with_suffix('.json'))
				items.append({
					'name': info.name if info else path.stem,
					'timestamp': format_time(info.start_time) if info else path.stem,  # Assuming file name is timestamp
					'length': format_seconds(info.length_seconds) if info else '--',
					'max_motion': info.max_motion if info else '--',
					'max_sad': info.max_sad if info else '--'
				})
		return flask.render_template('captures.html', items=items)


	@app.route('/captures/download/<name>')
	def download_capture(name):
		"""Download the selected file"""
		return flask.send_from_directory(video_dir, name + '.mp4', as_attachment=False)


	@app.route('/captures/play/<name>')
	def play_capture(name):
		"""Play the selected file"""
		return flask.render_template('play.html', name=name)

	@app.route('/captures/graphs/<name>/<graph_type>')
	def graph_image(name, graph_type):
		"""Return the graph image for the given name"""
		path = None
		if graph_type == 'motion':
			path = grapher.get_motion_image(name)
		elif graph_type == 'sad':
			path = grapher.get_sad_image(name)
		else:
			flask.abort(400, f'Unknown graph type {graph_type}')

		if path is not None and path.exists():
			return flask.send_file(path)
		else:
			flask.abort(404, f'Could not find "{graph_type}" graph image for {name}')

	return app


def format_time(t):
	return datetime.fromtimestamp(t / 1000000, tz=timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')

def format_seconds(s):
	return f'{int(s/60):0d}m:{int(s%60):02d}s'


def run(app, host, port):
	print('Starting web server...')
	server = threading.Thread(target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False), daemon=True)
	server.start()
	print(f'Web server is running on port {port}')
	return server