"""
QR65 Bridge Service Wrapper
===========================
Runs qr65_bridge.py in the background and restarts it if it ever exits.
Started at logon by the "QR65 BLE Bridge" scheduled task (.pyw = no console window).

The bridge writes its own rotating log (qr65_bridge.log). Its output is NOT piped through this
wrapper, so the bridge keeps working even if this wrapper is stopped. Anything the bridge prints
to stderr before its logging starts (e.g. an import error) lands in qr65_bridge_stderr.log.
"""

import logging
import logging.handlers
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_SCRIPT = os.path.join(SCRIPT_DIR, "qr65_bridge.py")
LOG_FILE = os.path.join(SCRIPT_DIR, "qr65_service.log")
STDERR_FILE = os.path.join(SCRIPT_DIR, "qr65_bridge_stderr.log")
PID_FILE = os.path.join(SCRIPT_DIR, "qr65_bridge.pid")

RESTART_DELAY = 5       # seconds between restart attempts
MAX_RAPID_RESTARTS = 5  # max restarts within the window below
RAPID_WINDOW = 60       # seconds - if too many restarts in this window, back off
BACKOFF_DELAY = 60      # seconds to wait after too many rapid restarts

handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=200_000, backupCount=1, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
log = logging.getLogger("qr65.service")
log.setLevel(logging.INFO)
log.addHandler(handler)


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def run():
    write_pid()
    log.info("service wrapper started (PID %d)", os.getpid())
    restart_times = []

    while True:
        log.info("starting bridge: %s", BRIDGE_SCRIPT)
        try:
            with open(STDERR_FILE, "w", encoding="utf-8") as err:
                proc = subprocess.Popen(
                    [sys.executable, BRIDGE_SCRIPT],
                    cwd=SCRIPT_DIR,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=err,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                log.info("bridge running (PID %d)", proc.pid)
                exit_code = proc.wait()
            log.info("bridge exited with code %d (see qr65_bridge.log / qr65_bridge_stderr.log)", exit_code)
        except Exception as exc:
            log.error("failed to start bridge: %s", exc)

        now = time.time()
        restart_times.append(now)
        restart_times = [t for t in restart_times if now - t < RAPID_WINDOW]
        if len(restart_times) >= MAX_RAPID_RESTARTS:
            log.warning("too many restarts (%d in %ds), backing off %ds",
                        len(restart_times), RAPID_WINDOW, BACKOFF_DELAY)
            time.sleep(BACKOFF_DELAY)
            restart_times.clear()
        else:
            time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log.info("service wrapper stopped")
    finally:
        remove_pid()
