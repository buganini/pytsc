"""Click CLI following brother_ql's global options and command organization."""

import json
from dataclasses import asdict
from functools import wraps
from pathlib import Path

import click

from . import TSPLRaster, __version__, convert, discover, send
from .analyze import analyze as inspect_job
from .analyze import bitmap_image
from .conversion import prepare_image
from .errors import PrintError
from .labels import LabelsManager
from .models import MODELS


def errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, OSError, RuntimeError) as exc:
            if kwargs.get("as_json"):
                result = dict(exc.result) if isinstance(exc, PrintError) else {"outcome": "error"}
                result["error"] = str(exc)
                click.echo(json.dumps(result))
                raise click.exceptions.Exit(1) from exc
            raise click.ClickException(str(exc)) from exc

    return wrapped


def emit(value, as_json):
    click.echo(json.dumps(value, ensure_ascii=False, indent=None if as_json else 2))


@click.group()
@click.option(
    "-b",
    "--backend",
    type=click.Choice(["serial", "cups"]),
    default="serial",
    envvar="PYTSC_BACKEND",
    show_default=True,
)
@click.option(
    "-m",
    "--model",
    type=click.Choice(list(MODELS)),
    default="TTP-342",
    envvar="PYTSC_MODEL",
    show_default=True,
)
@click.option(
    "-p",
    "--printer",
    envvar="PYTSC_PRINTER",
    help="Serial device path / COM3, or CUPS queue name / cups://QUEUE.",
)
@click.option(
    "--baudrate",
    type=click.IntRange(1),
    default=9600,
    envvar="PYTSC_BAUDRATE",
    show_default=True,
)
@click.option("--parity", type=click.Choice(["N", "E", "O"]), default="N", show_default=True)
@click.option("--stopbits", type=click.Choice(["1", "2"]), default="1", show_default=True)
@click.option(
    "--flow-control",
    type=click.Choice(["none", "rtscts", "dsrdtr"]),
    default="none",
    show_default=True,
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0, min_open=True),
    default=120,
    help="Transport submission deadline, seconds.",
)
@click.option("--debug", is_flag=True, help="Log transmission size and port to stderr.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, **options):
    """Convert images to TSPL and send to serial or CUPS label printers (experimental)."""
    ctx.ensure_object(dict)
    ctx.obj.update(options)


def transmit(ctx, data, as_json):
    options = ctx.obj
    if not options["printer"]:
        raise ValueError("Use --printer or PYTSC_PRINTER to select a printer")
    if options["debug"]:
        click.echo(
            f"Submitting {len(data)} bytes to {options['printer']} via {options['backend']}",
            err=True,
        )
    transport_options = {"timeout": options["timeout"]}
    if options["backend"] == "serial":
        transport_options.update(
            baudrate=options["baudrate"],
            parity=options["parity"],
            stopbits=int(options["stopbits"]),
            flow_control=options["flow_control"],
        )
    result = send(data, options["printer"], options["backend"], **transport_options)
    if as_json:
        emit(result, True)
    else:
        click.echo(
            f"{result['outcome']}: {result['bytes_sent']} bytes"
            + (f"; CUPS job {result['job_id']}" if result.get("job_id") else "")
            + "; physical printing is not confirmed."
        )


@cli.command("discover")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@errors
def discover_command(ctx, as_json):
    """List serial ports, or CUPS queues and unconfigured devices."""
    emit(discover(ctx.obj["backend"]), as_json)


@cli.command("info")
@click.argument("topic", type=click.Choice(["models", "labels", "env"]), default="models")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@errors
def info(ctx, topic, as_json):
    """List profiles, label syntax, or effective connection settings."""
    if topic == "models":
        result = [asdict(model) for model in MODELS.values()]
    elif topic == "labels":
        result = dict(
            format="WIDTHxHEIGHT mm",
            examples=["50x30", "40x30"],
            note="Examples, not verified stock",
        )
    else:
        result = ctx.obj
    emit(result, as_json)


def image_options(fn):
    for decorator in reversed(
        [
            click.argument(
                "images",
                nargs=-1,
                required=True,
                type=click.Path(exists=True, dir_okay=False, path_type=Path),
            ),
            click.option(
                "-l",
                "--label",
                required=True,
                envvar="PYTSC_LABEL",
                help="WIDTHxHEIGHT in mm",
            ),
            click.option(
                "-r",
                "--rotate",
                type=click.Choice(["auto", "0", "90", "180", "270"]),
                default="auto",
            ),
            click.option(
                "-t",
                "--threshold",
                type=click.IntRange(0, 100),
                default=70,
                help="Lower values print more black, as in brother_ql.",
            ),
            click.option("-d", "--dither", is_flag=True),
            click.option("--fit", type=click.Choice(["strict", "contain"]), default="strict"),
            click.option(
                "--gap",
                type=click.FloatRange(0),
                default=2,
                help="Gap / black-mark height in mm.",
            ),
            click.option(
                "--media",
                type=click.Choice(["gap", "black-mark", "continuous"]),
                default="gap",
            ),
            click.option("--density", type=click.IntRange(0, 15), default=8),
            click.option("--direction", type=click.IntRange(0, 1), default=1),
            click.option(
                "--speed",
                type=float,
                help="Inches/second; omitted to retain printer setting.",
            ),
            click.option("--copies", type=click.IntRange(1, 65535), default=1),
        ]
    ):
        fn = decorator(fn)
    return fn


@cli.command("print")
@image_options
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@errors
def print_command(ctx, images, label, as_json, **options):
    """Print IMAGE [IMAGE] ... as one-bit TSPL bitmaps."""
    if not ctx.obj["printer"]:
        raise ValueError("Use --printer or PYTSC_PRINTER to select a printer")
    data = convert(TSPLRaster(ctx.obj["model"]), images, label, **options)
    transmit(ctx, data, as_json)


@cli.command("convert")
@image_options
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.pass_context
@errors
def convert_command(ctx, images, label, output, **options):
    """Write raw TSPL instructions offline."""
    data = convert(TSPLRaster(ctx.obj["model"]), images, label, **options)
    output.write_bytes(data)


@cli.command("preview")
@image_options
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.pass_context
@errors
def preview(ctx, images, label, output, **options):
    """Preview one converted bitmap; excludes physical direction and feed offsets."""
    if len(images) != 1:
        raise ValueError("preview requires exactly one image")
    raster = TSPLRaster(ctx.obj["model"])
    convert(raster, images, label, **options)
    size = LabelsManager().get_label_by_identifier(label).pixels(raster.model.dots_per_mm)
    image = prepare_image(
        images[0],
        size,
        **{k: options[k] for k in ("rotate", "threshold", "dither", "fit")},
    )
    image.save(output, format="PNG")


@cli.command("send")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@errors
def send_command(ctx, file, as_json):
    """Send a raw TSPL instruction file unchanged."""
    transmit(ctx, file.read_bytes(), as_json)


@cli.command("analyze")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True)
@errors
def analyze_command(file, output_dir, as_json):
    """Inspect ASCII/ uncompressed BITMAP instructions; optionally extract PNGs."""
    records = inspect_job(file.read_bytes())
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        if "data" in record:
            if output_dir:
                bitmap_image(record).save(output_dir / f"bitmap-{index:03d}.png")
            record["byte_count"] = len(record.pop("data"))
    emit(records, as_json)
