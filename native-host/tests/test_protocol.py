import io
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twitch_local_exporter.protocol import ProtocolError, read_message, write_message


class ProtocolTests(unittest.TestCase):
    def test_round_trip_message(self):
        stream = io.BytesIO()
        write_message(stream, {"id": "1", "text": "字幕"})
        stream.seek(0)

        self.assertEqual(read_message(stream), {"id": "1", "text": "字幕"})

    def test_empty_stream_returns_none(self):
        self.assertIsNone(read_message(io.BytesIO()))

    def test_rejects_oversized_payload(self):
        stream = io.BytesIO(struct.pack("<I", 1024 * 1024 + 1))
        with self.assertRaises(ProtocolError):
            read_message(stream)


if __name__ == "__main__":
    unittest.main()
