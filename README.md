# Edifier QR65 ↔ SignalRGB bridge

Sync the RGB lighting of **Edifier QR65** speakers with **SignalRGB** on Windows, so the speakers follow your other RGB components. Works whether the speakers play over **USB or Bluetooth**.

*Unofficial hobby project, not affiliated with Edifier or WhirlwindFX/SignalRGB. Use at your own risk.*

🇩🇪 Deutsche Anleitung: [ANLEITUNG.txt](ANLEITUNG.txt)

## Features

- Finds your QR65 automatically. No pairing and no admin rights needed.
- Stays connected and reconnects on its own after PC restarts, sleep, or switching between USB and Bluetooth audio.
- Only the newest color is sent, rate-limited, so the lights don't stutter.
- Color calibration page with per-channel strength and gamma, to match your other RGB hardware exactly.
- A Windows notification tells you when the speaker needs one button press (see [Limitations](#limitations)).

## Quick start

1. Install [Python 3.10+](https://www.python.org/downloads/). Tick **"Add python.exe to PATH"**.
2. Download the zip from [**Releases**](../../releases/latest) and unzip it to a permanent folder.
3. Quit SignalRGB, then switch the QR65 to **Bluetooth mode** with its input button.
4. Double-click **`install.cmd`**.
5. Start SignalRGB. **Edifier QR65** appears under Devices; place it in your layout.
6. Calibrate the colors at <http://127.0.0.1:5297/calibrate>.

Full instructions and troubleshooting are in [README.txt](README.txt).

## How it works

```
SignalRGB ──plugin──▶ HTTP 127.0.0.1:5297 ──▶ qr65_bridge.py ──Bluetooth LE──▶ QR65
```

- `signalrgb-plugin/`: SignalRGB device plugin. It posts the speaker's canvas color to the bridge.
- `qr65_bridge.py`: local HTTP server, reachable from this PC only. It wires the parts below together.
- `qr65_link.py`: BLE connection manager (find, connect, reconnect).
- `qr65_discover.py`: automatic speaker discovery.
- `qr65_sender.py`: latest-color-wins sender.
- `qr65_color.py`: calibration.
- `qr65_protocol.py`: QR65 BLE packet format (static color command `0x6B`).

## Limitations

When the QR65 is **powered on directly in USB mode**, its Bluetooth radio stays completely off and nothing on the PC can wake it. The bridge detects this and shows a notification: press the input button twice (**USB → Bluetooth → USB**) and it reconnects within seconds. Everything else is automatic.

## Development

```
python -m unittest discover -s tests -t .
```

## License

[MIT](LICENSE)
