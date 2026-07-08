Download `twitch-local-exporter-vX.Y.Z-windows.zip`, extract it, then load this folder in your browser extension page:

```text
extension
```

Copy the generated extension ID, then run the native host installer from the extracted release folder:

```powershell
.\scripts\install-native.ps1 -ExtensionId <extension-id> -Browser chrome
.\scripts\update-tools.ps1
```

Use `-Browser edge`, `-Browser chromium`, `-Browser vivaldi`, or omit `-Browser` to register all supported browser registry paths.

The release bundle includes the extension files, native host files, installer scripts, release notes, and privacy notes. `update-tools.ps1` downloads `yt-dlp`, TwitchDownloaderCLI, Deno, FFmpeg/FFprobe, whisper.cpp, and the selected Whisper model into `%LOCALAPPDATA%\TwitchLocalExporter\tools`.
