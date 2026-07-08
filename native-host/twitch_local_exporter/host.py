from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .commands import run_probe, summarize_probe
from .cookies import temporary_cookie_file
from .dialogs import choose_output_folder
from .jobs import JobManager
from .protocol import ProtocolError, read_message, write_message
from .tools import require_tools, status as tools_status


class NativeHost:
    def __init__(self):
        self._write_lock = threading.Lock()
        self._jobs = JobManager(self.send_event)

    def run(self) -> None:
        while True:
            try:
                message = read_message(sys.stdin.buffer)
                if message is None:
                    return
                self.handle_message(message)
            except ProtocolError as error:
                self.send_event({"event": "error", "jobId": "protocol", "error": str(error)})
                return
            except Exception as error:
                self.send_response({}, ok=False, error=str(error))

    def handle_message(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        try:
            action = message.get("action")
            if action == "ping":
                payload = tools_status()
            elif action == "probe":
                payload = {"probe": self.probe(str(message.get("url") or ""), message.get("cookies"))}
            elif action == "export":
                payload = {"jobId": self._jobs.start_export(message.get("request") or {})}
            elif action == "jobStatus":
                payload = {"job": self._jobs.status(str(message.get("jobId") or ""))}
            elif action == "cancelJob":
                payload = {"job": self._jobs.cancel(str(message.get("jobId") or ""))}
            elif action == "openOutputFolder":
                payload = self.open_output_folder(str(message.get("path") or ""))
            elif action == "chooseOutputFolder":
                path = choose_output_folder(str(message.get("initialDir") or ""))
                payload = {"path": path, "cancelled": not bool(path)}
            elif action == "updateTools":
                payload = {"jobId": self._jobs.start_update_tools()}
            else:
                raise RuntimeError(f"Unknown action: {action}")
            self.send_response({"id": request_id, **payload})
        except Exception as error:
            self.send_response({"id": request_id}, ok=False, error=str(error))

    def probe(self, url: str, cookies: Any = None) -> dict[str, Any]:
        if not url:
            raise RuntimeError("Probe request is missing a URL")
        tools = require_tools(["yt-dlp.exe"])
        with temporary_cookie_file(cookies) as cookie_file:
            return summarize_probe(run_probe(tools["yt-dlp.exe"], url, cookie_file=cookie_file))

    def open_output_folder(self, value: str) -> dict[str, Any]:
        if not value:
            raise RuntimeError("Missing path")
        path = Path(value)
        target = path.parent if path.is_file() else path
        if not target.exists() and path.parent.exists():
            target = path.parent
        subprocess.Popen(["explorer.exe", str(target)])
        return {"opened": True, "path": str(target)}

    def send_response(self, payload: dict[str, Any], *, ok: bool = True, error: str = "") -> None:
        message = {"ok": ok, "version": __version__, **payload}
        if error:
            message["error"] = error
        with self._write_lock:
            write_message(sys.stdout.buffer, message)

    def send_event(self, payload: dict[str, Any]) -> None:
        message = {"ok": True, **payload}
        with self._write_lock:
            write_message(sys.stdout.buffer, message)


def main() -> None:
    try:
        NativeHost().run()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise
