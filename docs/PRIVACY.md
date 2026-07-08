# Privacy

Twitch Local Exporter stores extension preferences in `chrome.storage.sync`, including default output folder text, preferred export mode, default formats, chat settings, and subtitle settings.

Media, subtitle, and chat export jobs are processed locally by the native host. The extension does not collect analytics, send generated media to a remote service, or use cloud transcription.

The native host writes exported files to the selected local output folder and stores downloaded helper tools under `%LOCALAPPDATA%\TwitchLocalExporter\tools`.

Use this tool only for Twitch VODs you own or are authorized to export.
