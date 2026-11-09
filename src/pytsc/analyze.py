"""Inspect raw TSPL without splitting binary bitmap payloads at newlines.

Supports uncompressed BITMAP commands and line-oriented ASCII commands.
This is an inspector, not an interpreter for every TSPL command or download format.
"""

import re

from PIL import Image

_HEADER = re.compile(rb"BITMAP (\d+),(\d+),(\d+),(\d+),([012]),")


def analyze(data):
    records = []
    offset = 0
    while offset < len(data):
        if data.startswith(b"BITMAP ", offset):
            match = _HEADER.match(data, offset)
            if not match:
                raise ValueError(f"Invalid or unsupported BITMAP header at byte {offset}")
            x, y, stride, height, mode = map(int, match.groups())
            if not 0 < stride <= 8192 or not 0 < height <= 65535:
                raise ValueError("Invalid bitmap dimensions")
            end = match.end() + stride * height
            if data[end : end + 2] != b"\r\n":
                raise ValueError("Truncated BITMAP or missing CRLF terminator")
            records.append(
                dict(
                    command="BITMAP",
                    x=x,
                    y=y,
                    width_bytes=stride,
                    height=height,
                    mode=mode,
                    data=data[match.end() : end],
                )
            )
            offset = end + 2
        else:
            end = data.find(b"\r\n", offset)
            if end < 0:
                raise ValueError("Missing CRLF command terminator")
            command = data[offset:end].decode("ascii")
            if any(ord(c) < 32 or ord(c) > 126 for c in command):
                raise ValueError("Unsupported binary command")
            records.append(dict(command=command))
            offset = end + 2
    return records


def bitmap_image(record):
    return Image.frombytes("1", (record["width_bytes"] * 8, record["height"]), record["data"])
