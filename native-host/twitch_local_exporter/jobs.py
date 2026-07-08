from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .commands import (
    build_audio_command,
    build_chat_command,
    build_download_audio_command,
    build_ffmpeg_wav_command,
    build_subtitle_command,
    build_video_command,
    build_whisper_command,
    chat_output_format,
    choose_subtitle_language,
    output_base_path,
    run_probe,
)
from .config import update_script_path
from .cookies import temporary_cookie_file
from .subtitle_text import convert_chinese_subtitle_file, should_convert_chinese_subtitles
from .tools import require_tools


ProgressSink = Callable[[dict[str, Any]], None]
PERCENT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d+)?)%")


@dataclass
class Job:
    job_id: str
    kind: str
    request: dict[str, Any]
    status: str = "queued"
    percent: float = 0.0
    detail: str = ""
    output_path: str = ""
    error: str = ""
    process: subprocess.Popen[str] | None = None
    cancel_requested: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "jobId": self.job_id,
                "kind": self.kind,
                "event": self.status,
                "percent": self.percent,
                "detail": self.detail,
                "outputPath": self.output_path,
                "error": self.error
            }


class JobManager:
    def __init__(self, send_event: ProgressSink):
        self._send_event = send_event
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start_export(self, request: dict[str, Any]) -> str:
        kind = str(request.get("kind") or "")
        if kind not in {"video", "audio", "subtitles", "chat"}:
            raise RuntimeError(f"Unsupported export kind: {kind}")
        if not request.get("url"):
            raise RuntimeError("Export request is missing a URL")

        job = Job(str(uuid.uuid4()), kind, dict(request))
        self._register(job)
        threading.Thread(target=self._run_export, args=(job,), daemon=True).start()
        self._emit(job, "queued", 0, "Queued")
        return job.job_id

    def start_update_tools(self) -> str:
        script = update_script_path()
        if not script.exists():
            raise RuntimeError(f"Update script was not found: {script}")

        job = Job(str(uuid.uuid4()), "updateTools", {"script": str(script)})
        self._register(job)
        threading.Thread(target=self._run_update_tools, args=(job, script), daemon=True).start()
        self._emit(job, "queued", 0, "Queued")
        return job.job_id

    def status(self, job_id: str) -> dict[str, Any]:
        job = self._get(job_id)
        return job.snapshot()

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self._get(job_id)
        with job.lock:
            job.cancel_requested = True
            process = job.process
        if process and process.poll() is None:
            process.terminate()
        self._emit(job, "cancelled", job.percent, "Cancelled")
        return job.snapshot()

    def _register(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def _get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            raise RuntimeError(f"Unknown job: {job_id}")
        return job

    def _run_export(self, job: Job) -> None:
        try:
            if job.kind == "video":
                self._run_video(job)
            elif job.kind == "audio":
                self._run_audio(job)
            elif job.kind == "subtitles":
                self._run_subtitles(job)
            elif job.kind == "chat":
                self._run_chat(job)
        except Cancelled:
            self._emit(job, "cancelled", job.percent, "Cancelled")
        except Exception as error:
            self._emit(job, "error", job.percent, str(error), error=str(error))

    def _run_video(self, job: Job) -> None:
        tools = require_tools(["yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe"])
        base = output_base_path(job.request)
        base.parent.mkdir(parents=True, exist_ok=True)
        output_template = Path(f"{base}.%(ext)s")
        with temporary_cookie_file(job.request.get("cookies")) as cookie_file:
            command = build_video_command(tools["yt-dlp.exe"], job.request, output_template, cookie_file)
            self._run_command(job, command, "progress", 5, 95)
        output = newest_matching_output(base.parent, base.name, ["mp4", "mkv", "webm", "mov"])
        self._emit(job, "done", 100, str(output), output_path=str(output))

    def _run_audio(self, job: Job) -> None:
        tools = require_tools(["yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe"])
        base = output_base_path(job.request)
        base.parent.mkdir(parents=True, exist_ok=True)
        output_template = Path(f"{base}.%(ext)s")
        with temporary_cookie_file(job.request.get("cookies")) as cookie_file:
            command = build_audio_command(tools["yt-dlp.exe"], job.request, output_template, cookie_file)
            self._run_command(job, command, "progress", 5, 95)
        output = newest_matching_output(base.parent, base.name, ["m4a", "mp3", "opus", "wav", "aac", "flac"])
        self._emit(job, "done", 100, str(output), output_path=str(output))

    def _run_chat(self, job: Job) -> None:
        tools = require_tools(["TwitchDownloaderCLI.exe"])
        base = output_base_path(job.request)
        base.parent.mkdir(parents=True, exist_ok=True)
        chat = job.request.get("chat") if isinstance(job.request.get("chat"), dict) else {}
        output = Path(f"{base}.chat.{chat_output_format(chat)}")
        command = build_chat_command(tools["TwitchDownloaderCLI.exe"], job.request, output)
        self._run_command(job, command, "progress", 5, 95)
        if not output.exists():
            raise RuntimeError(f"Twitch chat command finished without producing {output.name}")
        self._emit(job, "done", 100, str(output), output_path=str(output))

    def _run_subtitles(self, job: Job) -> None:
        subtitles = job.request.get("subtitles") if isinstance(job.request.get("subtitles"), dict) else {}
        source = str(subtitles.get("source") or "auto")
        language = str(subtitles.get("language") or "auto")
        subtitle_format = str(subtitles.get("format") or "srt")

        tools = require_tools(["yt-dlp.exe"])
        with temporary_cookie_file(job.request.get("cookies")) as cookie_file:
            probe_summary = job.request.get("probe") if isinstance(job.request.get("probe"), dict) else None
            if probe_summary:
                info: dict[str, Any] = {
                    "id": probe_summary.get("id") or job.request.get("vodId") or job.request.get("videoId"),
                    "title": probe_summary.get("title") or job.request.get("title")
                }
            else:
                self._emit(job, "progress", 2, "Reading video metadata")
                info = run_probe(tools["yt-dlp.exe"], job.request["url"], cookie_file=cookie_file)

            base = output_base_path(job.request, info)
            base.parent.mkdir(parents=True, exist_ok=True)

            chosen_language, has_twitch_caption = choose_subtitle_from_probe_summary(probe_summary, language) if probe_summary else choose_subtitle_language(info, language)
            if source != "whisper" and has_twitch_caption:
                command = build_subtitle_command(tools["yt-dlp.exe"], job.request, Path(f"{base}.%(ext)s"), chosen_language, cookie_file)
                self._run_command(job, command, "progress", 5, 70)
                output = newest_matching_output(base.parent, base.name, [subtitle_format], required=False)
                if output:
                    self._convert_chinese_subtitles_if_requested(job, output, subtitles, language, chosen_language)
                    self._emit(job, "done", 100, str(output), output_path=str(output))
                    return
                if source == "twitch":
                    raise RuntimeError("Twitch caption command finished without producing a subtitle file")

            if source == "twitch":
                raise RuntimeError("No matching Twitch caption track was found")

            self._run_whisper(job, base, language, subtitle_format, subtitles, cookie_file)

    def _run_whisper(
        self,
        job: Job,
        output_base: Path,
        language: str,
        subtitle_format: str,
        subtitles: dict[str, Any] | None = None,
        cookie_file: Path | None = None
    ) -> None:
        tools = require_tools(["yt-dlp.exe", "ffmpeg.exe", "whisper-cli.exe", "model"], job.request.get("whisperModel") or "small")
        with tempfile.TemporaryDirectory(prefix="twitch-local-exporter-") as temp:
            temp_dir = Path(temp)
            audio_template = temp_dir / "source.%(ext)s"
            self._run_command(
                job,
                build_download_audio_command(tools["yt-dlp.exe"], job.request["url"], audio_template, cookie_file),
                "progress",
                5,
                40
            )
            source_audio = newest_matching_output(temp_dir, "source", ["m4a", "mp4", "webm", "opus", "mp3", "aac", "wav"])
            wav_path = temp_dir / "audio.wav"
            self._run_command(
                job,
                build_ffmpeg_wav_command(tools["ffmpeg.exe"], source_audio, wav_path),
                "postprocess",
                45,
                55
            )
            self._run_command(
                job,
                build_whisper_command(
                    tools["whisper-cli.exe"],
                    tools["model"],
                    wav_path,
                    output_base,
                    language,
                    subtitle_format
                ),
                "postprocess",
                55,
                98
            )
        output = Path(f"{output_base}.{subtitle_format}")
        if not output.exists():
            output = newest_matching_output(output_base.parent, output_base.name, [subtitle_format])
        self._convert_chinese_subtitles_if_requested(job, output, subtitles, language)
        self._emit(job, "done", 100, str(output), output_path=str(output))

    def _convert_chinese_subtitles_if_requested(
        self,
        job: Job,
        output: Path,
        subtitles: dict[str, Any] | None,
        *languages: Any
    ) -> None:
        if not should_convert_chinese_subtitles(subtitles, *languages):
            return
        self._emit(job, "postprocess", 99, "Converting Chinese subtitles")
        convert_chinese_subtitle_file(output, (subtitles or {}).get("chineseScript"))

    def _run_update_tools(self, job: Job, script: Path) -> None:
        try:
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script)
            ]
            self._run_command(job, command, "progress", 5, 95)
            self._emit(job, "done", 100, "Tools updated")
        except Cancelled:
            self._emit(job, "cancelled", job.percent, "Cancelled")
        except Exception as error:
            self._emit(job, "error", job.percent, str(error), error=str(error))

    def _run_command(self, job: Job, command: list[str], phase: str, start: float, end: float) -> None:
        self._raise_if_cancelled(job)
        self._emit(job, phase, start, command_summary(command))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        with job.lock:
            job.process = process

        tail: list[str] = []
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                self._raise_if_cancelled(job)
                line = raw_line.strip()
                if not line:
                    continue
                tail = (tail + [line])[-12:]
                percent = interpolate_progress(line, start, end)
                self._emit(job, phase, percent if percent is not None else job.percent, line)
            code = process.wait()
            if code != 0:
                raise RuntimeError("\n".join(tail) or f"Command failed with exit code {code}")
        finally:
            with job.lock:
                if job.process is process:
                    job.process = None

    def _raise_if_cancelled(self, job: Job) -> None:
        with job.lock:
            cancelled = job.cancel_requested
            process = job.process
        if cancelled:
            if process and process.poll() is None:
                process.terminate()
            raise Cancelled()

    def _emit(
        self,
        job: Job,
        event: str,
        percent: float,
        detail: str,
        *,
        output_path: str = "",
        error: str = ""
    ) -> None:
        with job.lock:
            job.status = event
            job.percent = max(0.0, min(100.0, float(percent)))
            job.detail = detail
            if output_path:
                job.output_path = output_path
            if error:
                job.error = error
            payload = {
                "jobId": job.job_id,
                "kind": job.kind,
                "event": job.status,
                "percent": job.percent,
                "detail": job.detail,
                "outputPath": job.output_path,
                "error": job.error
            }
        payload.update({"version": __version__})
        self._send_event(payload)


class Cancelled(Exception):
    pass


def interpolate_progress(line: str, start: float, end: float) -> float | None:
    match = PERCENT_PATTERN.search(line)
    if not match:
        return None
    percent = float(match.group(1))
    return start + ((end - start) * (percent / 100.0))


def command_summary(command: list[str]) -> str:
    executable = Path(command[0]).name if command else "command"
    return f"Running {executable}"


def newest_matching_output(directory: Path, base_name: str, extensions: list[str], *, required: bool = True) -> Path | None:
    extension_set = {f".{extension.lower().lstrip('.')}" for extension in extensions}
    candidates = [
        path for path in directory.iterdir()
        if path.is_file()
        and path.name.startswith(base_name)
        and path.suffix.lower() in extension_set
    ]
    if candidates:
        return max(candidates, key=lambda path: path.stat().st_mtime)
    if required:
        raise RuntimeError(f"No output file was produced in {directory}. Files: {describe_directory_files(directory)}")
    return None


def describe_directory_files(directory: Path) -> str:
    try:
        files = sorted(path.name for path in directory.iterdir())
    except OSError:
        return "unavailable"
    return ", ".join(files[:20]) if files else "empty"


def choose_subtitle_from_probe_summary(probe: dict[str, Any] | None, requested: str) -> tuple[str, bool]:
    if not probe:
        return "auto", False
    tracks = probe.get("subtitles") if isinstance(probe.get("subtitles"), list) else []
    usable = [
        track for track in tracks
        if isinstance(track, dict) and track.get("lang") and track.get("lang") != "live_chat"
    ]
    if requested and requested != "auto":
        return requested, any(track.get("lang") == requested for track in usable)
    manual = next((track for track in usable if track.get("type") == "manual"), None)
    if manual:
        return str(manual["lang"]), True
    automatic = next((track for track in usable if track.get("type") == "auto"), None)
    if automatic:
        return str(automatic["lang"]), True
    return "auto", False
