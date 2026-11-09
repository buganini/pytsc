import random

import pytest
from click.testing import CliRunner
from PIL import Image, ImageDraw

from pytsc import TSPLRaster, convert
from pytsc.cli import cli
from pytsc.conversion import prepare_image


def render_bars(data, size):
    image = Image.new("1", size, 1)
    draw = ImageDraw.Draw(image)
    for line in data.decode("ascii").splitlines():
        if line.startswith("BAR "):
            x, y, w, h = map(int, line[4:].split(","))
            assert w > 0 and h > 0
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=0)
    return image


@pytest.mark.parametrize("size", [(1, 1), (9, 17), (32, 24)])
def test_random_pixels_roundtrip(size):
    rng = random.Random(17)
    image = Image.new("1", size)
    image.putdata([rng.choice([0, 255]) for _ in range(size[0] * size[1])])
    data = TSPLRaster().bars(image, x=3, y=4).data
    expected = Image.new("1", (size[0] + 3, size[1] + 4), 1)
    expected.paste(image, (3, 4))
    assert render_bars(data, expected.size).tobytes() == expected.tobytes()


def test_solid_and_empty_merge():
    assert TSPLRaster().bars(Image.new("1", (240, 240), 0)).data == b"BAR 0,0,240,240\r\n"
    assert TSPLRaster().bars(Image.new("1", (240, 240), 1)).data == b""


def test_full_dithered_image_roundtrip():
    source = "examples/test-label.png"
    size = (1224, 914)
    data = convert(
        TSPLRaster(), [source], "102x76.2", fit="contain", dither=True, gap=3, raster_mode="bar"
    )
    expected = prepare_image(source, size, fit="contain", dither=True)
    assert render_bars(data, size).tobytes() == expected.tobytes()
    assert b"BITMAP " not in data
    assert data.count(b"PRINT 1,1\r\n") == 1


def test_cli_bar(tmp_path):
    out = tmp_path / "job.tspl"
    result = CliRunner().invoke(
        cli,
        [
            "convert",
            "-l",
            "50x30",
            "--raster-mode",
            "bar",
            "examples/test-label.png",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert b"BAR " in out.read_bytes()
    result = CliRunner().invoke(
        cli,
        [
            "convert",
            "-l",
            "50x30",
            "--raster-mode",
            "bar",
            "--bitmap-rows",
            "128",
            "examples/test-label.png",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 1
