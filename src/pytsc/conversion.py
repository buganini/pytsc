"""Offline image conversion; no device access."""

from PIL import Image, ImageOps

from .labels import LabelsManager
from .raster import TSPLRaster, integer


def prepare_image(source, size, *, rotate="auto", threshold=70, dither=False, fit="strict"):
    if isinstance(source, Image.Image):
        image = source.copy()
    else:
        with Image.open(source) as opened:
            image = opened.copy()
    image = ImageOps.exif_transpose(image).convert("RGBA")
    bg = Image.new("RGBA", image.size, "white")
    bg.alpha_composite(image)
    image = bg.convert("L")
    if rotate == "auto":
        if image.size != size and image.size[::-1] == size:
            image = image.rotate(90, expand=True)
    elif str(rotate) in ("0", "90", "180", "270"):
        image = image.rotate(int(rotate), expand=True)
    else:
        raise ValueError("rotate must be auto, 0, 90, 180 or 270")
    if fit not in ("strict", "contain"):
        raise ValueError("fit must be strict or contain")
    if fit == "contain":
        image = ImageOps.pad(image, size, method=Image.Resampling.LANCZOS, color=255)
    elif image.size != size:
        raise ValueError(
            f"Image is {image.size}; expected {size} pixels. Use fit='contain' to resize explicitly"
        )
    integer(threshold, "threshold", 0, 100)
    if dither:
        return image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    # Match brother_ql/pyniim: lower threshold => more black.
    cutoff = 255 * (100 - threshold) / 100
    return image.point(lambda p: 255 if p >= 255 or p > cutoff else 0, mode="1")


def convert(
    raster,
    images,
    label,
    *,
    rotate="auto",
    threshold=70,
    dither=False,
    fit="strict",
    copies=1,
    gap=2,
    media="gap",
    density=8,
    direction=1,
    speed=None,
):
    """Return raw TSPL bytes and replace raster.data only after successful conversion."""
    integer(copies, "copies", 1)
    label = LabelsManager().get_label_by_identifier(label)
    job = TSPLRaster(raster.model.identifier)
    job.setup(label, gap=gap, media=media, density=density, direction=direction, speed=speed)
    count = 0
    for source in images:
        image = prepare_image(
            source,
            label.pixels(raster.model.dots_per_mm),
            rotate=rotate,
            threshold=threshold,
            dither=dither,
            fit=fit,
        )
        job.clear().bitmap(image).print_label(copies)
        count += 1
    if not count:
        raise ValueError("At least one image is required")
    raster.data = job.data
    return raster.data
