export function Name() { return "Edifier QR65"; }
export function Version() { return "1.0.0"; }
export function Type() { return "network"; }
export function Publisher() { return "Custom"; }
export function Size() { return [1, 1]; }
export function DefaultPosition() { return [150, 200]; }
export function DefaultScale() { return 8.0; }
export function DefaultComponentBrand() { return "Edifier"; }

export function ControllableParameters() {
	return [
		{"property": "bridgePort", "group": "settings", "label": "Bridge Port", "type": "number", "min": "1024", "max": "65535", "default": "5297"},
		{"property": "shutdownColor", "group": "lighting", "label": "Shutdown Color", "type": "color", "default": "#000000"},
		{"property": "brightness", "group": "lighting", "label": "Brightness", "type": "number", "min": "0", "max": "100", "default": "100"},
	];
}

// Controller class - manages the device instance
class EdifierQR65Controller {
	constructor(value) {
		this.mac = value.mac;
		this.id = value.mac;
		this.name = value.name;
		this.ip = value.ip;
		this.port = value.port;
		this.connected = false;
		this.announced = false;
		this.readyToAnnounce = false;

		this.verifyDevice();
	}

	verifyDevice() {
		const instance = this;
		const xhr = new XMLHttpRequest();
		xhr.open("GET", "http://" + this.ip + ":" + this.port + "/ping", true);

		xhr.onreadystatechange = function() {
			if (xhr.readyState === 4 && xhr.status === 200) {
				instance.readyToAnnounce = true;
				instance.connected = true;
				service.log("Edifier QR65 bridge verified at " + instance.ip + ":" + instance.port);
				service.updateController(instance);
			}
		};

		xhr.send();
	}

	updateWithValue(value) {
		this.ip = value.ip;
		this.port = value.port;
		this.name = value.name;
		service.updateController(this);
	}

	Update() {
		if (this.readyToAnnounce && !this.announced) {
			service.announceController(this);
			this.announced = true;
			service.log("Announced Edifier QR65");
		}
	}
}

// Discovery Service - SignalRGB calls this to find network devices
export function DiscoveryService() {
	this.IconUrl = "";
	this.MDns = [];

	this.isValidIP = function(ip) {
		return /^(\d{1,3}\.){3}\d{1,3}$/.test(ip);
	};

	this.Discovered = function(value) {
		service.log("Discovered: " + value.name + " at " + value.ip);

		const controller = service.getController(value.mac);

		if (controller === undefined) {
			service.addController(new EdifierQR65Controller(value));
		} else {
			controller.updateWithValue(value);
		}
	};

	this.Initialize = function() {
		service.log("Edifier QR65 discovery initialized");
	};

	// Retry discovery until the bridge answers: at logon SignalRGB may start before the bridge does.
	this.lastDiscoverAttempt = 0;
	const REDISCOVER_MS = 10000;

	this.Update = function() {
		try {
			const controllers = service.controllers;
			if ((!controllers || controllers.length === 0) && Date.now() - this.lastDiscoverAttempt > REDISCOVER_MS) {
				this.forceDiscover("127.0.0.1");
			}
			if (controllers) {
				for (let i = 0; i < controllers.length; i++) {
					const ctrl = controllers[i];
					if (ctrl && ctrl.obj && typeof ctrl.obj.Update === "function") {
						ctrl.obj.Update();
					}
				}
			}
		} catch (e) {
			service.log("Update error: " + e);
		}
	};

	this.forceDiscover = function(ipaddress) {
		const ip = ipaddress || "127.0.0.1";
		const port = 5297;

		if (!this.isValidIP(ip)) {
			service.log("Invalid IP: " + ip);
			return;
		}

		service.log("Checking for Edifier QR65 bridge at " + ip + ":" + port);
		this.lastDiscoverAttempt = Date.now();

		const instance = this;
		const xhr = new XMLHttpRequest();
		xhr.open("GET", "http://" + ip + ":" + port + "/ping", true);

		xhr.onreadystatechange = function() {
			if (xhr.readyState === 4 && xhr.status === 200) {
				const mac = "edifier-qr65-" + ip.replace(/\./g, "-");

				instance.Discovered({
					mac: mac,
					name: "Edifier QR65",
					ip: ip,
					port: port,
				});
			}
		};

		xhr.send();
	};

	// Auto-discover on localhost at startup
	this.forceDiscover("127.0.0.1");
}

// Device runtime
let lastR = -1;
let lastG = -1;
let lastB = -1;
let lastSendTime = 0;
const MIN_INTERVAL_MS = 50;
// Resend the current color this often even if unchanged, so a restarted/reconnected bridge
// gets the color without waiting for the effect to change (the bridge drops duplicates).
const KEEPALIVE_MS = 1000;

function getBaseUrl() {
	const port = bridgePort || 5297;
	return "http://127.0.0.1:" + port;
}

export function Initialize() {
	lastR = -1;
	lastG = -1;
	lastB = -1;

	const xhr = new XMLHttpRequest();
	xhr.open("GET", getBaseUrl() + "/ping", true);
	xhr.send();
}

export function Render() {
	const color = device.color(0, 0);
	const r = color[0];
	const g = color[1];
	const b = color[2];

	const now = Date.now();
	const unchanged = r === lastR && g === lastG && b === lastB;
	if (unchanged && now - lastSendTime < KEEPALIVE_MS) {
		return;
	}
	if (now - lastSendTime < MIN_INTERVAL_MS) {
		return;
	}

	lastR = r;
	lastG = g;
	lastB = b;
	lastSendTime = now;

	const br = brightness !== undefined ? brightness : 100;
	const url = getBaseUrl() + "/color?r=" + r + "&g=" + g + "&b=" + b + "&brightness=" + br;

	const xhr = new XMLHttpRequest();
	xhr.open("GET", url, true);
	xhr.send();
}

export function Shutdown() {
	const color = shutdownColor || "#000000";
	const r = parseInt(color.substr(1, 2), 16);
	const g = parseInt(color.substr(3, 2), 16);
	const b = parseInt(color.substr(5, 2), 16);

	const url = getBaseUrl() + "/color?r=" + r + "&g=" + g + "&b=" + b + "&brightness=0";

	const xhr = new XMLHttpRequest();
	xhr.open("GET", url, true);
	xhr.send();
}
