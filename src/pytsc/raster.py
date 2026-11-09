"""TSPL command builder. BITMAP uses MSB first, 0=black and 1=white."""

import math

from .labels import LabelsManager
from .models import ModelsManager


def integer(value, name, low=0, high=65535):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def number(value, name, low=0, high=1000):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be finite and in {low}..{high}")
    return f"{value:g}"


def quoted(value):
    if not isinstance(value, str) or any(ord(c) < 32 or c in '\\"' or ord(c) > 126 for c in value):
        raise ValueError(
            "Native text must be printable ASCII without quotes or backslashes; rasterize Unicode text"
        )
    return f'"{value}"'


class TSPLRaster:
    def __init__(self, model="TTP-342"):
        self.model = ModelsManager().get_model_by_identifier(model)
        self.data = b""

    def command(self, command):
        """Append one explicit ASCII command; raw device commands are caller-controlled."""
        if "\r" in command or "\n" in command:
            raise ValueError("Use one command per call")
        self.data += command.encode("ascii") + b"\r\n"
        return self

    def setup(self, label, *, gap=2, media="gap", density=8, direction=1, speed=None):
        label = LabelsManager().get_label_by_identifier(label)
        if label.width_mm > self.model.max_width_mm:
            raise ValueError("Label exceeds model print width")
        integer(density, "density", 0, 15)
        integer(direction, "direction", 0, 1)
        number(gap, "gap")
        if media not in ("gap", "black-mark", "continuous"):
            raise ValueError("Unknown media type")
        if speed is not None:
            number(speed, "speed", 0.1, 20)
        self.command(f"SIZE {label.width_mm:g} mm,{label.height_mm:g} mm")
        if media == "continuous":
            self.command("GAP 0 mm,0 mm")
        else:
            self.command(f"{'BLINE' if media == 'black-mark' else 'GAP'} {gap:g} mm,0 mm")
        self.command(f"DENSITY {density}").command(f"DIRECTION {direction}")
        self.command("REFERENCE 0,0").command("OFFSET 0 mm")
        if speed is not None:
            self.command(f"SPEED {speed:g}")
        return self

    def clear(self):
        return self.command("CLS")

    def bitmap(self, image, x=0, y=0, *, rows=0):
        from PIL import Image

        integer(x, "x")
        integer(y, "y")
        if image.mode != "1":
            raise ValueError("BITMAP requires a monochrome mode-1 image")
        integer(rows, "bitmap rows", 0)
        integer(y + image.height - 1, "last bitmap row")
        stride = (image.width + 7) // 8
        # Pillow normally pads unused bits with zero (black). Pad white explicitly.
        padded = Image.new("1", (stride * 8, image.height), 1)
        padded.paste(image)
        data = padded.tobytes()
        step = rows or image.height
        for start in range(0, image.height, step):
            height = min(step, image.height - start)
            self.data += (
                f"BITMAP {x},{y + start},{stride},{height},0,".encode()
                + data[start * stride : (start + height) * stride]
                + b"\r\n"
            )
        return self

    def bars(self, image, x=0, y=0):
        """Render black pixels with ASCII BARs, merging equal runs vertically.

        White pixels are transparent; call clear() first for a fresh label.
        """
        integer(x, "x")
        integer(y, "y")
        if image.mode != "1":
            raise ValueError("BAR raster requires a monochrome mode-1 image")
        integer(x + image.width - 1, "last BAR column")
        integer(y + image.height - 1, "last BAR row")
        pixels = image.load()
        active = {}
        commands = []

        def emit(run, start, end):
            left, width = run
            commands.append(f"BAR {x + left},{y + start},{width},{end - start}\r\n")

        for row in range(image.height):
            runs = set()
            col = 0
            while col < image.width:
                if pixels[col, row]:
                    col += 1
                    continue
                start = col
                while col < image.width and not pixels[col, row]:
                    col += 1
                runs.add((start, col - start))
            for run in sorted(active.keys() - runs):
                emit(run, active.pop(run), row)
            for run in sorted(runs):
                active.setdefault(run, row)
        for run in sorted(active):
            emit(run, active[run], image.height)
        self.data += "".join(commands).encode("ascii")
        return self

    def text(self, x, y, text, font="3", rotation=0, x_mul=1, y_mul=1):
        integer(x, "x")
        integer(y, "y")
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Invalid rotation")
        integer(x_mul, "x_mul", 1, 10)
        integer(y_mul, "y_mul", 1, 10)
        return self.command(
            f"TEXT {x},{y},{quoted(font)},{rotation},{x_mul},{y_mul},{quoted(text)}"
        )

    def barcode(
        self,
        x,
        y,
        data,
        height=80,
        symbology="128",
        readable=1,
        rotation=0,
        narrow=2,
        wide=2,
    ):
        for name, value in (("x", x), ("y", y)):
            integer(value, name)
        for name, value in (("height", height), ("narrow", narrow), ("wide", wide)):
            integer(value, name, 1)
        integer(readable, "readable", 0, 1)
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Invalid rotation")
        return self.command(
            f"BARCODE {x},{y},{quoted(symbology)},{height},{readable},{rotation},{narrow},{wide},{quoted(data)}"
        )

    def print_label(self, copies=1):
        integer(copies, "copies", 1)
        return self.command(f"PRINT 1,{copies}")
