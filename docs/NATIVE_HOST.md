# Native Host Notes

## Message Protocol

Messages use the Chrome native messaging framing: a 4-byte little-endian payload length followed by a UTF-8 JSON object.

Extension requests include an `id` and one of these actions:

- `ping`
- `probe`
- `export`
- `jobStatus`
- `cancelJob`
- `openOutputFolder`
- `chooseOutputFolder`
- `updateTools`

Responses echo `id` for direct requests. Job updates are pushed as standalone messages containing `jobId`, `event`, `percent`, `detail`, and optionally `outputPath` or `error`.

## Tool Locations

Bundled tools are preferred from:

```text
%LOCALAPPDATA%\TwitchLocalExporter\tools
```

The host falls back to PATH for development when a bundled executable is missing.

Required tools by export type:

- Video/audio: `yt-dlp.exe`, `ffmpeg.exe`, `ffprobe.exe`
- Chat: `TwitchDownloaderCLI.exe`
- Subtitle fallback: `yt-dlp.exe`, `ffmpeg.exe`, `whisper-cli.exe`, and `models\ggml-small.bin` by default
- Optional `yt-dlp` JavaScript runtime: `deno.exe` or another supported runtime on PATH (`node`, `quickjs`, or `bun`)

## Output Naming

Files use:

```text
YYYY-MM-DD - title [vodId].ext
YYYY-MM-DD - title [vodId].chat.json
```

Invalid Windows filename characters and `%` are replaced with `_`.
