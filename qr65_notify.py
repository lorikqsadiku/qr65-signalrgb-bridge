"""Fire-and-forget Windows toast notification (via qr65_notify.ps1)."""

import logging
import os
import subprocess

log = logging.getLogger("qr65.notify")

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr65_notify.ps1")


def notify(title: str, message: str, runner=subprocess.Popen) -> None:
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden", "-File", SCRIPT, "-Title", title, "-Message", message]
    try:
        runner(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        log.warning("could not show notification: %s", exc)
