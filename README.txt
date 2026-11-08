EDIFIER QR65 + SIGNALRGB  -  RGB SYNC
=====================================

Makes the RGB lighting of your Edifier QR65 follow SignalRGB, in sync with your other RGB
components - whether the speakers play over USB or Bluetooth.
(Deutsche Anleitung: ANLEITUNG.txt)

Unofficial hobby project, not affiliated with Edifier or SignalRGB. Use at your own risk.


REQUIREMENTS
------------
- Windows 10 or 11 with Bluetooth (Bluetooth LE / 4.0 or newer)
- SignalRGB (https://signalrgb.com)
- Python 3.10 or newer: https://www.python.org/downloads/
  IMPORTANT: tick "Add python.exe to PATH" during setup.
- The QR65 does NOT need to be paired with Windows. No admin rights needed.


INSTALLATION (once, about 5 minutes)
------------------------------------
1. Unzip to a permanent place, e.g.  Documents\QR65-SignalRGB-Bridge
   Don't move the folder afterwards - the autostart points to it.

2. Quit SignalRGB (right-click its tray icon -> Exit).

3. Switch the QR65 on and press its input button until it is in BLUETOOTH mode.
   That is when the PC can find it.

4. Double-click  install.cmd  and follow the window.
   It installs the Python packages, copies the SignalRGB plugin, finds your QR65,
   sets up autostart and starts the bridge.

5. Start SignalRGB. "Edifier QR65" appears under Devices - place it in your layout.

6. Done. You can switch the QR65 back to USB now; the lights stay in sync.


COLOR CALIBRATION (recommended)
-------------------------------
The QR65's LEDs look different from other RGB hardware out of the box. Open:

    http://127.0.0.1:5297/calibrate

1. In SignalRGB set the "Solid Color" effect to WHITE.
2. Use the "Channel strength" sliders until the white matches
   (bluish -> lower Blue, greenish -> lower Green, pinkish -> lower Red).
3. Check red, green, blue and mixed colors (orange, purple, teal); use "Gamma" for mixes.
Everything is saved automatically.
Tip: on the author's QR65, Red 100% / Green 54% / Blue 54% (gamma 1.00) matched - a good start.


DAY TO DAY
----------
- Automatic: PC restart, sleep, switching between USB and Bluetooth.
- ONE exception: if the QR65 is switched off and on (power switch or power cut) and starts in
  USB mode, its Bluetooth is completely off - no PC can wake it. You get a Windows notification:
  press the input button TWICE (USB -> Bluetooth -> USB) and the sync is back within seconds.
- With Do Not Disturb on, the notification only lands in the notification center (Win+N).
  To let it pop up anyway: Settings -> System -> Notifications -> Set priority notifications ->
  add "Windows PowerShell".


TROUBLESHOOTING
---------------
- Status:            http://127.0.0.1:5297/status
    "state": "connected" / "searching" / "asleep" (= press the input button twice)
- Restart the bridge: double-click  restart.cmd
- Log:               qr65_bridge.log  in this folder
- Bluetooth on the PC must be switched on.
- Speaker missing in SignalRGB: restart SignalRGB once.
- Wrong device found (e.g. Edifier headphones)? Set "device_address" to "" in qr65_config.json
  and run restart.cmd while only the QR65 is in Bluetooth mode.


UNINSTALL
---------
Double-click  uninstall.cmd , restart SignalRGB, then delete this folder.


FILES
-----
qr65_bridge.py            the bridge (HTTP server for SignalRGB + Bluetooth connection)
qr65_link.py              finds/connects/reconnects the speaker
qr65_discover.py          finds a QR65 automatically
qr65_sender.py            sends only the newest color, rate limited
qr65_color.py             color calibration math
qr65_protocol.py          QR65 Bluetooth packet format
qr65_notify.py/.ps1       Windows notification
qr65_calibrate.html       calibration page
qr65_bridge_service.pyw   keeps the bridge running (started by the autostart task)
signalrgb-plugin\         SignalRGB device plugin
tests\                    automated tests:  python -m unittest discover -s tests -t .
