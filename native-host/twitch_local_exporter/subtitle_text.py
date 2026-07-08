from __future__ import annotations

from pathlib import Path
from typing import Any


_OPENCC_CONFIGS = {
    "traditional_tw": "s2twp",
}
_CONVERTERS: dict[str, Any] = {}


def normalize_chinese_script(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in {"traditional", "traditional_tw", "tw", "zh_tw", "s2twp"}:
        return "traditional_tw"
    return "original"


def is_chinese_language(language: Any) -> bool:
    text = str(language or "").strip().lower().replace("_", "-")
    return text in {"zh", "chi", "zho", "chinese", "mandarin"} or text.startswith("zh-")


def should_convert_chinese_subtitles(subtitles: dict[str, Any] | None, *languages: Any) -> bool:
    if normalize_chinese_script((subtitles or {}).get("chineseScript")) != "traditional_tw":
        return False
    return any(is_chinese_language(language) for language in languages)


def convert_chinese_subtitle_file(path: Path, script: Any) -> bool:
    config = _OPENCC_CONFIGS.get(normalize_chinese_script(script))
    if not config:
        return False

    converter = _opencc_converter(config)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        original = handle.read()
    converted = converter.convert(original)
    if converted == original:
        return False

    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(converted)
    return True


def _opencc_converter(config: str) -> Any:
    converter = _CONVERTERS.get(config)
    if converter is not None:
        return converter

    try:
        from opencc import OpenCC
    except ModuleNotFoundError as error:
        if error.name != "opencc":
            raise
        raise RuntimeError(
            "Chinese subtitle conversion requires opencc-python-reimplemented. "
            "Run scripts/install-native.ps1 again, or install it with "
            "python -m pip install opencc-python-reimplemented."
        ) from error

    converter = OpenCC(config)
    _CONVERTERS[config] = converter
    return converter
