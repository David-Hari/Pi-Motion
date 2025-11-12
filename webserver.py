import io
import threading
import logging
from pathlib import Path
from flask import Flask, Response, request, redirect, url_for, send_from_directory, render_template_string

# Simple templates
INDEX_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Camera</title>
<style>
body { font-family: sans-serif; background:#111; color:#eee; margin:20px; }
.container { max-width: 1000px; margin: auto; }
.card { background:#1b1b1b; padding:14px; border-radius:6px; margin-bottom:14px; }
a { color: #9cf; }
img.live { width: 100%; height: auto; border: 1px solid #333; }
</style>
</head>
<body>
<div class="container">
  <h1>Camera</h1>
  <div class="card">
    <h2>Live</h2>
    <p>Live MJPEG preview (click to open full-size)</p>
    <a href="{{ url_for('live') }}"><img class="live" src="{{ url_for('live') }}" alt="live preview"></a>
  </div>

  <div class="card">
    <h2>Captures</h2>
    <p>Recorded events (most recent first)</p>
    <ul>
    {% for f in files %}
      <li>
        {{ f.name }} —
        <a href="{{ url_for('download_capture', filename=f.name) }}">download</a>
        &nbsp;|&nbsp;
        <a href="{{ url_for('play_capture', filename=f.name) }}">play</a>
      </li>
    {% endfor %}
    </ul>
  </div>
</div>
</body>
</html>
"""

PLAY_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Play {{ name }}</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif;padding:20px">
<h1>{{ name }}</h1>
<video controls autoplay style="max-width:100%">
  <source src="{{ url_for('download_capture', filename=name) }}" type="video/x-matroska">
  Your browser does not support the video tag.
</video>
<p><a href="{{ url_for('index') }}">Back</a></p>
</body>
</html>
"""

def create(recorder, video_dir: Path):
	print('Setting up web server')
	log = logging.getLogger('werkzeug')
	log.setLevel(logging.ERROR)
	app = Flask(__name__, static_folder=None)

	def mjpeg_generator():
		"""Helper to produce MJPEG frames from the camera."""
		camera = recorder.camera
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
			print("Client disconnected from live stream")
		except Exception as e:
			print(f'Failed to provide MJPEG stream. {e}')
			#TODO: Send the error message to client
		finally:
			print("Stopped sending preview")


	@app.route('/')
	def index():
		return redirect(url_for('live'))


	@app.route('/live')
	def live():
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
		return render_template_string(INDEX_HTML, files=files)


	@app.route('/captures/download/<filename>')
	def download_capture(filename):
		return send_from_directory(video_dir, filename, as_attachment=False)


	@app.route('/captures/play/<filename>')
	def play_capture(filename):
		return render_template_string(PLAY_HTML, name=filename)

	return app


def run(app, host, port):
	print('Starting web server...')
	server = threading.Thread(target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False), daemon=True)
	server.start()
	print(f'Web server is running on port {port}')
	return server