import io
import threading
import logging
from pathlib import Path
import flask
from flask import Flask, Response, url_for


def create(camera, video_dir: Path):
	print('Setting up web server')

	log = logging.getLogger('werkzeug')
	log.setLevel(logging.ERROR)

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
			#TODO: Show error page with the error message
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
		files = []
		if video_dir.exists():
			for p in sorted(video_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
				if p.is_file():
					files.append(p)
		return flask.render_template('captures.html', files=files)


	@app.route('/captures/download/<filename>')
	def download_capture(filename):
		"""Download the selected file"""
		return flask.send_from_directory(video_dir, filename, as_attachment=False)


	@app.route('/captures/play/<filename>')
	def play_capture(filename):
		"""Play the selected file"""
		return flask.render_template('play.html', name=filename)

	return app


def run(app, host, port):
	print('Starting web server...')
	server = threading.Thread(target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False), daemon=True)
	server.start()
	print(f'Web server is running on port {port}')
	return server