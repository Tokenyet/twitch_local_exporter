import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twitch_local_exporter.commands import (
    build_audio_command,
    build_chat_command,
    build_download_audio_command,
    build_probe_command,
    build_video_command,
    chat_output_format,
    choose_subtitle_language,
    output_base_path,
    sanitize_filename,
    summarize_probe,
    video_format_selector,
    whisper_audio_format_selector,
)


class CommandTests(unittest.TestCase):
    def test_sanitize_filename_removes_windows_invalid_chars_and_percent(self):
        self.assertEqual(sanitize_filename(' bad:video/%name* '), "bad_video__name")

    def test_output_base_contains_date_title_and_video_id(self):
        base = output_base_path({
            "title": "A/B test",
            "videoId": "abc123",
            "outputDir": "C:/Exports"
        })
        self.assertEqual(base.parent.as_posix(), "C:/Exports")
        self.assertIn("A_B test [abc123]", base.name)

    def test_video_format_selector_does_not_upscale(self):
        self.assertEqual(video_format_selector("720"), "bv*[height<=720]+ba/b[height<=720]/b")
        self.assertEqual(video_format_selector("best"), "bv*+ba/b")

    def test_build_probe_command_uses_json_skip_download(self):
        command = build_probe_command(Path("yt-dlp.exe"), "https://www.twitch.tv/videos/123456789")
        self.assertIn("-J", command)
        self.assertIn("--skip-download", command)
        self.assertIn("--retries", command)
        self.assertIn("30", command)
        self.assertIn("--http-chunk-size", command)

    def test_build_video_command_contains_mp4_merge_and_recode(self):
        command = build_video_command(
            Path("yt-dlp.exe"),
            {"url": "https://www.twitch.tv/videos/123456789", "quality": "1080"},
            Path("out.%(ext)s")
        )
        self.assertIn("--merge-output-format", command)
        self.assertIn("--recode-video", command)
        self.assertIn("bv*[height<=1080]+ba/b[height<=1080]/b", command)

    def test_build_audio_command_uses_extract_audio(self):
        command = build_audio_command(
            Path("yt-dlp.exe"),
            {"url": "https://www.twitch.tv/videos/123456789", "audioFormat": "mp3"},
            Path("out.%(ext)s")
        )
        self.assertIn("-x", command)
        self.assertIn("--audio-format", command)
        self.assertIn("mp3", command)

    def test_build_download_audio_command_uses_whisper_specific_selector(self):
        command = build_download_audio_command(
            Path("yt-dlp.exe"),
            "https://www.twitch.tv/videos/123456789",
            Path("source.%(ext)s")
        )
        self.assertIn("-f", command)
        self.assertIn(whisper_audio_format_selector(), command)
        self.assertIn("ba[ext=m4a][abr<=128]", whisper_audio_format_selector())

    def test_build_chat_command_uses_twitch_downloader_cli(self):
        command = build_chat_command(
            Path("TwitchDownloaderCLI.exe"),
            {
                "url": "https://www.twitch.tv/videos/123456789",
                "chat": {"format": "txt", "embedImages": True}
            },
            Path("chat.txt")
        )
        self.assertEqual(command[1], "chatdownload")
        self.assertIn("--id", command)
        self.assertIn("https://www.twitch.tv/videos/123456789", command)
        self.assertIn("--output", command)
        self.assertIn("chat.txt", command)
        self.assertIn("--timestamp-format", command)
        self.assertIn("--embed-images", command)
        self.assertEqual(chat_output_format({"format": "bad"}), "json")

    def test_summarize_probe_reduces_formats_and_subtitles(self):
        probe = summarize_probe({
            "id": "abc",
            "title": "Demo",
            "duration": 30,
            "formats": [
                {"height": 1080, "vcodec": "av01", "acodec": "none", "fps": 60, "ext": "mp4"},
                {"height": 720, "vcodec": "avc1", "acodec": "none", "fps": 30, "ext": "mp4"},
                {"vcodec": "none", "acodec": "mp4a", "abr": 128, "ext": "m4a"}
            ],
            "subtitles": {"en": [{"ext": "vtt", "name": "English"}]},
            "automatic_captions": {"ja": [{"ext": "vtt"}]}
        })

        self.assertEqual([item["height"] for item in probe["videoQualities"]], [1080, 720])
        self.assertEqual(probe["audioBitrates"], [128])
        self.assertEqual([item["lang"] for item in probe["subtitles"]], ["en", "ja"])

    def test_choose_subtitle_language_prefers_manual_then_auto(self):
        info = {
            "subtitles": {"zh-Hant": []},
            "automatic_captions": {"en": []}
        }
        self.assertEqual(choose_subtitle_language(info, "auto"), ("zh-Hant", True))
        self.assertEqual(choose_subtitle_language(info, "en"), ("en", True))
        self.assertEqual(choose_subtitle_language({}, "auto"), ("auto", False))


if __name__ == "__main__":
    unittest.main()
