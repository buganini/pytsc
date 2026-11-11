from io import BytesIO

import pytest
from PIL import Image

from pytsc import TSPLRaster, convert
from pytsc.analyze import analyze, bitmap_image
from pytsc.conversion import prepare_image


def test_bitmap_polarity_order_padding_and_binary_newlines():
    image = Image.new("1", (9, 2), 1)
    image.putpixel((0, 0), 0)
    image.putpixel((8, 1), 0)
    raster = TSPLRaster().bitmap(image)
    assert raster.data == b"BITMAP 0,0,2,2,0,\x7f\xff\xff\x7f\r\n"
    assert bitmap_image(analyze(raster.data)[0]).getpixel((0, 0)) == 0
    assert analyze(b"BITMAP 0,0,2,1,0,\r\n\r\nPRINT 1,1\r\n")[0]["data"] == b"\r\n"


def test_conversion_order_pages_and_copies():
    raster = TSPLRaster()
    data = convert(raster, [Image.new("1", (600, 360), 1)] * 2, "50x30", copies=2)
    assert data.startswith(b"SIZE 50 mm,30 mm\r\nGAP 2 mm,0 mm\r\n")
    assert data.count(b"CLS\r\n") == 2
    assert data.count(b"PRINT 1,2\r\n") == 2
    assert raster.data == data
    assert b"BITMAP 0,0,75,360,0," in data


def test_conversion_atomic_failure():
    raster = TSPLRaster()
    raster.data = b"previous"
    with pytest.raises(ValueError):
        convert(raster, [Image.new("1", (1, 1))], "50x30")
    assert raster.data == b"previous"


def test_rotation_transparency_and_file_input():
    image = Image.new("RGBA", (360, 600), (0, 0, 0, 0))
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    out = prepare_image(stream, (600, 360))
    assert out.size == (600, 360)
    assert out.getextrema() == (255, 255)


def test_fit_threshold_dither():
    image = Image.new("L", (1, 1), 128)
    assert prepare_image(image, (1, 1), threshold=70, dither=False).getpixel((0, 0)) == 255
    assert prepare_image(image, (1, 1), threshold=30, dither=False).getpixel((0, 0)) == 0
    assert prepare_image(image, (4, 8), fit="contain", dither=True).size == (4, 8)


@pytest.mark.parametrize(
    "options",
    [
        dict(copies=0),
        dict(copies=True),
        dict(gap=-1),
        dict(gap=float("nan")),
        dict(density=16),
        dict(media="bad"),
        dict(direction=2),
    ],
)
def test_invalid_options(options):
    with pytest.raises(ValueError):
        convert(TSPLRaster(), [Image.new("1", (600, 360))], "50x30", **options)


def test_native_commands_and_injection():
    raster = (
        TSPLRaster()
        .setup("50x30")
        .clear()
        .text(10, 10, "Hello")
        .barcode(10, 60, "12345")
        .print_label()
    )
    assert b'TEXT 10,10,"3",0,1,1,"Hello"\r\n' in raster.data
    with pytest.raises(ValueError):
        raster.text(0, 0, 'bad"\r\nPRINT 1,99')


@pytest.mark.parametrize("data", [b"BITMAP 0,0,2,1,0,a\r\n", b"CLS", b"BITMAP 0,0,2,1,3,aa\r\n"])
def test_analyze_rejects_invalid(data):
    with pytest.raises(ValueError):
        analyze(data)


@pytest.mark.parametrize("width,height,rows", [(1200, 720, 128), (9, 7, 3), (600, 360, 1000)])
def test_bitmap_strips_preserve_every_pixel(width, height, rows):
    image = Image.new("1", (width, height), 1)
    for y in range(height):
        image.putpixel((y % width, y), 0)
    single = analyze(TSPLRaster().bitmap(image).data)[0]
    chunks = analyze(TSPLRaster().bitmap(image, x=4, y=9, rows=rows).data)
    assert b"".join(chunk["data"] for chunk in chunks) == single["data"]
    assert [chunk["y"] for chunk in chunks] == list(range(9, height + 9, rows))
    assert all(chunk["x"] == 4 and chunk["height"] <= rows for chunk in chunks)


def test_large_conversion_strips_print_once():
    data = convert(
        TSPLRaster(), [Image.new("1", (600, 360))], "100x60", fit="contain", bitmap_rows=128
    )
    records = analyze(data)
    assert sum(r["command"] == "BITMAP" for r in records) == 6
    assert sum(r["command"] == "CLS" for r in records) == 1
    assert sum(r["command"] == "PRINT 1,1" for r in records) == 1
