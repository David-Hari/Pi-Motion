(function(){
	const video = document.getElementsByTagName('video')[0];
	const playButton = document.getElementsByClassName('play-button')[0];
	const prevFrameButton = document.getElementsByClassName('prev-frame-button')[0];
	const nextFrameButton = document.getElementsByClassName('next-frame-button')[0];
	const timeText = document.getElementsByClassName('time-text')[0];
	const progressBar = document.getElementsByClassName('progress-bar')[0];
	const bufferBar = document.getElementsByClassName('buffer-range')[0];
	const playedBar = document.getElementsByClassName('played-bar')[0];
	const thumb = document.getElementsByClassName('thumb')[0];


	function formatTime(s){
		if (!isFinite(s) || s <= 0) {
			return '0:00';
		}
		const mins = Math.floor(s / 60);
		const secs = Math.floor(s % 60).toString().padStart(2, '0');
		return `${mins}:${secs}`;
	}


	function updateTimeText(){
		const cur = formatTime(video.currentTime || 0);
		const dur = formatTime(video.duration || 0);
		timeText.textContent = `${cur} / ${dur}`;
	}


	/* Update played portion (0..100%) */
	function updatePlayed(){
		if (!isFinite(video.duration) || video.duration === 0) {
			playedBar.style.width = '0%';
			thumb.style.left = '0%';
			return;
		}
		const playPercent = (video.currentTime / video.duration) * 100;
		playedBar.style.width = playPercent + '%';
		thumb.style.left = playPercent + '%';
		progressBar.setAttribute('aria-valuenow', Math.round(playPercent));
		updateBuffered();
	}


	/* Update buffered range */
	function updateBuffered(){
		if (!isFinite(video.duration) || video.duration === 0) {
			return;
		}

		const ranges = video.buffered;
		for (let i = 0; i < ranges.length; i++){
			const end = ranges.end(i);
			// Only handle a single time range, the one closest to current time
			if (end > video.currentTime) {
				bufferBar.style.width = (end / video.duration) * 100 + '%';
				return;
			}
		}
	}



	/* Click / drag to seek */
	function seek(ev){
		if (!isFinite(video.duration) || video.duration === 0) {
			return;
		}
		const r = progressBar.getBoundingClientRect();
		const pos = Math.max(0, Math.min(r.width, ev.clientX - r.left));
		video.currentTime = Math.max(0, Math.min(video.duration, (pos / r.width) * video.duration));
		updatePlayed();
		updateTimeText();
	}

	let dragging = false;
	progressBar.addEventListener('mousedown', function(ev){
		dragging = true;
		document.body.style.userSelect = 'none';
		seek(ev);
	});

	thumb.addEventListener('mousedown', function(ev){
		dragging = true;
		document.body.style.userSelect = 'none';
		seek(ev);
	});

	document.addEventListener('mouseup', function(ev){
		if (dragging) {
			dragging = false;
			document.body.style.userSelect = '';
			seek(ev);
		}
	});

	document.addEventListener('mousemove', function(ev){
		if (dragging) {
			seek(ev);
		}
	});


	/* Play / pause toggle */
	playButton.addEventListener('click', function(){
		if (video.paused || video.ended) {
			video.play();
		}
		else {
			video.pause();
		}
	});

	document.addEventListener('keydown', function(e){
		if (e.code === 'Space') {
			e.preventDefault();
			playButton.click();
		}
	});


	/* Previous / next frame */
	function stepFrame(isForward){
		if (!isFinite(video.duration) || video.duration === 0) {
			return;
		}
		if (isForward) {
			pos = video.currentTime + (1.0 / window.videoFrameRate);
		}
		else {
			pos = video.currentTime - (1.0 / window.videoFrameRate);
		}
		video.currentTime = Math.max(0, Math.min(video.duration, pos));
		updatePlayed();
		updateTimeText();
	}

	prevFrameButton.addEventListener('click', function(){
		if (video.paused) {
			stepFrame(false);
		}
	});

	nextFrameButton.addEventListener('click', function(){
		if (video.paused) {
			stepFrame(true);
		}
	});


	/* Update play button text/icon */
	function updatePlayButton(){
		if (video.paused || video.ended) {
			playButton.textContent = '▶';
			playButton.setAttribute('aria-pressed', 'false');
		}
		else {
			playButton.textContent = '❚❚';
			playButton.setAttribute('aria-pressed', 'true');
		}
	}


	/* Events from video */
	video.addEventListener('timeupdate', function(){
		if (!dragging) {
			updatePlayed();
		}
		updateTimeText();
	});

	video.addEventListener('progress', function(){
		updateBuffered();
	});

	video.addEventListener('loadedmetadata', function(){
		updatePlayed();
		updateTimeText();
	});

	video.addEventListener('playing', updatePlayButton);
	video.addEventListener('pause', updatePlayButton);
	video.addEventListener('ended', updatePlayButton);


	/* Initial UI */
	updateTimeText();
	updateBuffered();
})();