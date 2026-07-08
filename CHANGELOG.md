# Changelog

## 0.1.0 - 2026-07-06

Initial Twitch-focused release.

### Added

- Chromium MV3 extension for exporting authorized Twitch VOD video, audio, subtitles, and chat through a local native messaging host.
- Export modes for MP4 video, audio-only files, SRT/VTT subtitles, and VOD chat logs.
- Twitch caption preference with local Whisper fallback or forced Whisper transcription.
- Optional Chinese subtitle conversion to Traditional Chinese (Taiwan) using OpenCC after SRT/VTT output is produced.
- TwitchDownloaderCLI chat export as JSON, HTML, or plain text.
- Windows native messaging host with local output folders, helper tool detection, job progress, cancellation, and output folder opening.
- Installer and uninstaller scripts for Chrome, Edge, Chromium, and Vivaldi native messaging registry entries.
- Tool updater for yt-dlp, TwitchDownloaderCLI, Deno, FFmpeg/FFprobe, whisper.cpp, and Whisper models.
- Source installer and native host build support for the OpenCC Python dependency used by Chinese subtitle conversion.
- GitHub Actions CI and tag-driven release packaging.

### Release Assets

- `twitch-local-exporter-v0.1.0-windows.zip`: complete Windows sideload bundle.
- `twitch-local-exporter-extension-v0.1.0.zip`: extension-only runtime package.
- `twitch-local-exporter-host-v0.1.0-windows-x64.exe`: standalone native host executable.
- `SHA256SUMS.txt`: checksums for downloadable release assets.
