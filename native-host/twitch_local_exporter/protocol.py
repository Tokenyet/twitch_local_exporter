from __future__ import annotations

import json
import struct
from typing import BinaryIO, Any


MAX_MESSAGE_SIZE = 1024 * 1024


class ProtocolError(RuntimeError):
    pass


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    raw_length = stream.read(4)
    if raw_length == b"":
      return None
    if len(raw_length) != 4:
        raise ProtocolError("Incomplete native message length header")

    length = struct.unpack("<I", raw_length)[0]
    if length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Native message is too large: {length}")

    payload = stream.read(length)
    if len(payload) != length:
        raise ProtocolError("Incomplete native message payload")

    try:
        message = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ProtocolError(f"Invalid JSON payload: {error}") from error

    if not isinstance(message, dict):
        raise ProtocolError("Native message payload must be a JSON object")
    return message


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Native response is too large: {len(payload)}")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()
