from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from .config import default_output_dir
from .tools import ffmpeg_location, yt_dlp_js_runtime_args


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f%]')
SPACE_RUN = re.compile(r"\s+")


def sanitize_filename(value: str, fallback: str = "twitch-vod") -> str:
    text = SPACE_RUN.sub(" ", str(value or "").strip())
    text = INVALID_FILENAME_CHARS.sub("_", text)
    text = text.strip(" ._")
    if not text:
        text = fallback
    return text[:120].rstrip(" ._") or fallback


def output_directory(value: str | None) -> Path:
    text = str(value or "").strip()
    return Path(text).expanduser() if text else default_output_dir()


def output_base_path(request: dict[str, Any], info: dict[str, Any] | None = None) -> Path:
    info = info or {}
    title = request.get("title") or info.get("title") or "twitch-vod"
    vod_id = request.get("vodId") or request.get("videoId") or info.get("id") or "unknown"
    filename = f"{date.today().isoformat()} - {sanitize_filename(title)} [{sanitize_filename(vod_id, 'id')}]"
    return output_directory(request.get("outputDir")) / filename


def summarize_probe(info: dict[str, Any]) -> dict[str, Any]:
    formats = info.get("formats") if isinstance(info.get("formats"), list) else []
    quality_by_height: dict[int, dict[str, Any]] = {}
    audio_bitrates: set[int] = set()
    audio_formats: set[str] = set()

    for item in formats:
        if not isinstance(item, dict):
            continue
        vcodec = item.get("vcodec") or "none"
        acodec = item.get("acodec") or "none"
        height = safe_int(item.get("height"))

        if vcodec != "none" and height:
            existing = quality_by_height.get(height, {"height": height, "fps": 0, "ext": item.get("ext") or ""})
            existing["fps"] = max(existing["fps"], safe_int(item.get("fps")) or 0)
            quality_by_height[height] = existing

        if acodec != "none" and vcodec == "none":
            bitrate = safe_int(item.get("abr") or item.get("tbr"))
            if bitrate:
                audio_bitrates.add(bitrate)
            if item.get("ext"):
                audio_formats.add(str(item["ext"]))

    subtitles = collect_subtitles(info.get("subtitles"), "manual")
    subtitles.extend(collect_subtitles(info.get("automatic_captions"), "auto"))

    return {
        "id": info.get("id") or "",
        "title": info.get("title") or "",
        "duration": safe_int(info.get("duration")) or 0,
        "thumbnail": info.get("thumbnail") or "",
        "webpageUrl": info.get("webpage_url") or "",
        "videoQualities": sorted(quality_by_height.values(), key=lambda value: value["height"], reverse=True),
        "audioBitrates": sorted(audio_bitrates, reverse=True),
        "audioFormats": sorted(audio_formats),
        "subtitles": subtitles
    }


def collect_subtitles(value: Any, kind: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    result = []
    for lang, formats in sorted(value.items()):
        if lang == "live_chat":
            continue
        extensions = []
        if isinstance(formats, list):
            extensions = sorted({str(item.get("ext")) for item in formats if isinstance(item, dict) and item.get("ext")})
        result.append({
            "lang": str(lang),
            "name": language_name(formats),
            "type": kind,
            "formats": extensions
        })
    return result


def language_name(formats: Any) -> str:
    if isinstance(formats, list):
        for item in formats:
            if isinstance(item, dict) and item.get("name"):
                return str(item["name"])
    return ""


def safe_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def build_probe_command(yt_dlp: Path, url: str, cookie_file: Path | None = None) -> list[str]:
    command = base_yt_dlp_command(yt_dlp, cookie_file)
    command.extend(["-J", "--skip-download", str(url)])
    return command


def run_probe(yt_dlp: Path, url: str, timeout: int = 90, cookie_file: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(
        build_probe_command(yt_dlp, url, cookie_file),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "yt-dlp probe failed").strip()
        raise RuntimeError(detail[-1200:])
    return json.loads(result.stdout)


def video_format_selector(quality: str | int | None) -> str:
    if str(quality or "best") == "best":
        return "bv*+ba/b"
    height = safe_int(quality)
    if not height:
        return "bv*+ba/b"
    return f"bv*[height<={height}]+ba/b[height<={height}]/b"


def build_video_command(yt_dlp: Path, request: dict[str, Any], output_template: Path, cookie_file: Path | None = None) -> list[str]:
    command = base_yt_dlp_command(yt_dlp, cookie_file)
    command.extend([
        "-f", video_format_selector(request.get("quality")),
        "--merge-output-format", "mp4",
        "--recode-video", "mp4"
    ])
    add_ffmpeg_location(command)
    command.extend(["-o", str(output_template), request["url"]])
    return command


def build_audio_command(yt_dlp: Path, request: dict[str, Any], output_template: Path, cookie_file: Path | None = None) -> list[str]:
    audio_format = str(request.get("audioFormat") or "m4a")
    command = base_yt_dlp_command(yt_dlp, cookie_file)
    command.extend(["-f", "ba/b", "-x", "--audio-format", audio_format, "--audio-quality", "0"])
    add_ffmpeg_location(command)
    command.extend(["-o", str(output_template), request["url"]])
    return command


def build_subtitle_command(yt_dlp: Path, request: dict[str, Any], output_template: Path, language: str, cookie_file: Path | None = None) -> list[str]:
    subtitles = request.get("subtitles") if isinstance(request.get("subtitles"), dict) else {}
    subtitle_format = str(subtitles.get("format") or "srt")
    command = base_yt_dlp_command(yt_dlp, cookie_file)
    command.extend([
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", language,
        "--sub-format", subtitle_format,
        "-o", str(output_template),
        request["url"]
    ])
    return command


def build_chat_command(twitch_downloader: Path, request: dict[str, Any], output_path: Path) -> list[str]:
    chat = request.get("chat") if isinstance(request.get("chat"), dict) else {}
    command = [
        str(twitch_downloader),
        "chatdownload",
        "--id", request["url"],
        "--output", str(output_path),
        "--collision", "Overwrite"
    ]
    if chat_output_format(chat) == "txt":
        command.extend(["--timestamp-format", "Relative"])
    if chat.get("embedImages"):
        command.append("--embed-images")
    return command


def chat_output_format(chat: dict[str, Any] | None) -> str:
    value = str((chat or {}).get("format") or "json").lower()
    return value if value in {"json", "html", "txt"} else "json"


def build_download_audio_command(yt_dlp: Path, url: str, output_template: Path, cookie_file: Path | None = None) -> list[str]:
    command = base_yt_dlp_command(yt_dlp, cookie_file)
    command.extend(["-f", whisper_audio_format_selector(), "-o", str(output_template), url])
    return command


def build_ffmpeg_wav_command(ffmpeg: Path, input_path: Path, output_path: Path) -> list[str]:
    return [
        str(ffmpeg),
        "-y",
        "-i", str(input_path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_path)
    ]


def build_whisper_command(
    whisper_cli: Path,
    model_path: Path,
    wav_path: Path,
    output_base: Path,
    language: str,
    subtitle_format: str
) -> list[str]:
    output_flag = "-ovtt" if subtitle_format == "vtt" else "-osrt"
    lang = "auto" if not language or language == "auto" else language
    return [
        str(whisper_cli),
        "-np",
        "-m", str(model_path),
        "-f", str(wav_path),
        "-l", lang,
        output_flag,
        "-of", str(output_base)
    ]


def base_yt_dlp_command(yt_dlp: Path, cookie_file: Path | None = None) -> list[str]:
    command = [
        str(yt_dlp),
        "--newline",
        "--no-playlist",
        "--restrict-filenames",
        "--socket-timeout", "30",
        "--retries", "30",
        "--fragment-retries", "30",
        "--file-access-retries", "10",
        "--extractor-retries", "5",
        "--retry-sleep", "http:exp=1:20",
        "--retry-sleep", "fragment:exp=1:20",
        "--http-chunk-size", "10M"
    ]
    command.extend(yt_dlp_js_runtime_args())
    if cookie_file:
        command.extend(["--cookies", str(cookie_file)])
    return command


def whisper_audio_format_selector() -> str:
    return "ba[ext=m4a][abr<=128]/ba[abr<=64]/ba[abr<=96]/ba[abr<=128]/ba"


def add_ffmpeg_location(command: list[str]) -> None:
    location = ffmpeg_location()
    if location:
        command.extend(["--ffmpeg-location", location])


def choose_subtitle_language(info: dict[str, Any], requested: str) -> tuple[str, bool]:
    if requested and requested != "auto":
        return requested, has_subtitle_language(info, requested)

    subtitles = info.get("subtitles")
    if isinstance(subtitles, dict):
        for lang in subtitles:
            if lang != "live_chat":
                return str(lang), True

    automatic = info.get("automatic_captions")
    if isinstance(automatic, dict):
        for lang in automatic:
            if lang != "live_chat":
                return str(lang), True

    return "auto", False


def has_subtitle_language(info: dict[str, Any], language: str) -> bool:
    for key in ("subtitles", "automatic_captions"):
        value = info.get(key)
        if isinstance(value, dict) and language in value:
            return True
    return False
