const controls = [
	'awb_mode', 'exposure_mode', 'exposure_compensation',
	'brightness', 'contrast', 'saturation', 'iso', 'sharpness',
	'hflip', 'vflip', 'rotation', 'video_denoise', 'annotate_text_size'
];

let pending = {};
let lastSend = 0;
const minInterval = 500; // ms


// Fetch camera settings and populate UI
function getValues() {
	fetch('/controls')
		.then(r => r.json())
		.then(values => {
			for (const k in values) {
				const el = document.getElementById(k);
				if (!el) {
					continue;
				}

				if (el.type === 'checkbox') {
					el.checked = values[k];
				}
				else {
					el.value = values[k];
				}
			}
		});
}


function queueSend(key, value) {
	console.log('queueSend', key, value);
	pending[key] = value;
	const now = Date.now();
	if (now - lastSend >= minInterval) {
		sendUpdate(pending);
		lastSend = Date.now();
		pending = {};
	}
	else {
		// schedule a send at next allowed time
		clearTimeout(queueSend.timer);
		queueSend.timer = setTimeout(sendUpdate, minInterval - (now - lastSend), pending);
	}
}


function sendUpdate(data) {
	console.log('sendUpdate', data);
	fetch('/controls', {
		method: 'POST',
		headers: {'Content-Type': 'application/json'},
		body: JSON.stringify(data)
	});
}


getValues();

for (const id of controls) {
	const element = document.getElementById(id);
	if (!element) {
		continue;
	}

	// For sliders, use input event (fires while sliding) and throttle to at most 2 updates per second
	if (element.type === 'range') {
		element.addEventListener('input', ev => {
        	queueSend(ev.target.id, Number(ev.target.value));
        });
	}
	else if (element.type === 'checkbox') {
		element.addEventListener('change', ev => {
        	sendUpdate({ [ev.target.id]: ev.target.checked });
        });
	}
	else if (element.type === 'number') {
		element.addEventListener('change', ev => {
        	sendUpdate({ [ev.target.id]: Number(ev.target.value) });
        });
	}
	else {
		element.addEventListener('change', ev => {
        	sendUpdate({ [ev.target.id]: ev.target.value });
        });
	}
}