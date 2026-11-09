# pytsc

Experimental Python library and CLI for TSC/TSPL label printers, with an API and
Click CLI modeled after [brother_ql](https://github.com/pklaus/brother_ql).
The current hardware target is **elitek TTP-342 through a Prolific PL2305
USB-to-IEEE-1284 adapter on macOS**, using direct PyUSB access. RS-232 via
**pyserial** and CUPS queues are also supported.
[pyniim](https://github.com/buganini/pyniim) informs the convenience API and
honest transmission-result reporting.

**Status: 0.1.0a1; experimental, with successful direct-USB physical tests.**
Two consecutive native/BITMAP comparison labels and one full dithered image
printed correctly with soft reset disabled. CUPS on this adapter still showed
corruption and stalls. Long-run reliability and exact geometry remain unverified;
see [hardware test notes](docs/HARDWARE_TESTING.md). TTP-342 uses a provisional
300 dpi / 12 dots per mm, 104 mm maximum-width profile. Network transport,
printer-status polling, cutting and automatic calibration are not implemented.

## Install

Python 3.11+; install this checkout (not a published PyPI release):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[usb]'
# On macOS, direct USB also requires system libusb: brew install libusb
pytsc --help
pytsc discover
```

Dependencies: Pillow for raster conversion, Click for CLI, pyserial for RS-232.
No Windows DLL or .NET runtime is needed. Serial discovery lists ports and adapter
metadata; it cannot identify the printer behind an adapter. No port is opened by
discovery, conversion or preview commands.

## Hardware test: print the supplied image

![Test label](examples/test-label.png)

`examples/test-label.png` is a **50 × 30 mm, 600 × 360 px** test image with
orientation markers, a 10 mm square, 1–4 dot lines, a grayscale ramp and 1 mm
ruler ticks. The examples enable `--dither` to approximate the grayscale ramp
with black-and-white dots. No Python example script is needed.
The tested media is **102 × 76.2 mm with a 3 mm gap**. Print through the
PL2305 adapter using the successful settings (soft reset is disabled by default):

```sh
pytsc discover --json
pytsc -p pyusb://067b:2305 --timeout 20 \
  print -l 102x76.2 --gap 3 --fit contain --dither examples/test-label.png
```

For a final repeatability check, repeat that command without rebooting or
reconnecting, then add `--copies 2` to check two-label feeding and alignment.
These checks have not yet been reported as completed.

Generate and inspect the same raster offline:

```sh
pytsc preview -l 102x76.2 --fit contain --dither examples/test-label.png -o /tmp/preview.png
pytsc convert -l 102x76.2 --gap 3 --fit contain --dither examples/test-label.png -o /tmp/test.tspl
pytsc analyze /tmp/test.tspl --output-dir /tmp/pytsc-bitmaps
```

For RS-232, use `-b serial -p /dev/cu.usbserial-YOUR_ADAPTER --baudrate 9600`
before `print`, substituting the actual port and printer settings. Serial settings
are unverified on this device. Windows ports such as `COM3`, Linux paths such as
`/dev/ttyUSB0`, and `serial:///dev/cu.usbserial-...` are accepted.

For other label sizes, explicitly resize with options such as
`print -l 40x30 --fit contain ...`. This also scales the 10 mm square and ruler,
so they can no longer be used to check physical dimensions. The default
`--fit strict` rejects images with mismatched dimensions. `--rotate auto` only
handles images whose width and height exactly match the swapped target dimensions.
The 300 dpi profile uses the printhead's actual 12 dots/mm, so 50 mm equals
600 dots rather than a value calculated using 300/25.4.

## CLI

Global options precede the command, as in brother_ql:

- `-b/--backend serial|cups|pyusb`, `-m/--model`, `-p/--printer`, `--debug`, `--version`.
- `--baudrate`, `--parity N|E|O`, `--stopbits 1|2` (8 data bits).
- `--flow-control none|rtscts|dsrdtr`; this must match the printer and cable.
- `--timeout 120`: whole-job transmission deadline, in seconds.

Commands: `discover`, `info models|labels|env`, `print`, `send`, `analyze`.
`convert` and `preview` are offline extensions. `print`, `send`, `discover`, `info`
and `analyze` support `--json`. Debug messages go to stderr.

Image commands accept `-l/--label WIDTHxHEIGHT`, `-r/--rotate`, `-t/--threshold`,
`-d/--dither`, `--fit`, `--gap`, `--media gap|black-mark|continuous`, `--density`,
`--direction`, `--speed` and `--copies`. Threshold is a percentage, default 70;
lower values produce more black, following brother_ql. Speed is omitted unless
requested, retaining the printer's current speed. Direction defaults to 1 and
must be verified physically. Preview shows the input raster, not media feeding
or firmware orientation. `analyze` extracts individual BITMAPs, not composited
native text/barcodes or a full emulation of TSPL.

Environment variables: `PYTSC_BACKEND`, `PYTSC_MODEL`, `PYTSC_PRINTER`,
`PYTSC_BAUDRATE`, `PYTSC_LABEL`.

## Python API

```python
from pytsc import Printer

with Printer("/dev/cu.usbserial-YOUR_ADAPTER", model="TTP-342", baudrate=9600) as printer:
    result = printer.print_image("examples/test-label.png", label="50x30", gap=2, dither=True)
```

The brother_ql-style split API keeps conversion independent of communication:

```python
from pytsc.raster import TSPLRaster
from pytsc.conversion import convert
from pytsc.backends.helpers import discover, send

raster = TSPLRaster("TTP-342")
instructions = convert(raster, images=["examples/test-label.png"], label="50x30", dither=True)
# instructions is raw bytes, suitable for saving as a .tspl file.
result = send(
    instructions,
    printer_identifier="/dev/cu.usbserial-YOUR_ADAPTER",
    backend_identifier="serial",
    baudrate=9600,
)
```

`convert()` accepts paths, Pillow images, or binary file objects readable by
Pillow. It composites transparency onto white, optionally rotates/resizes,
converts to monochrome, then emits `SIZE`, media settings, `CLS`, `BITMAP` and
`PRINT`. Multiple inputs produce sequential labels; multi-frame image files
only use the selected/first frame. Existing `raster.data` is replaced only after
successful conversion. SVG/PDF/text layout must be rasterized first.

Native commands are also available through the chainable builder:

```python
job = (
    TSPLRaster("TTP-342")
    .setup("50x30", gap=2)
    .clear()
    .text(24, 24, "Hello TSPL")
    .barcode(24, 80, "12345678", height=80)
    .print_label(copies=1)
)
# Send job.data with the same send() function.
```

Native text accepts printable ASCII without quotes/backslashes; for Chinese or
custom fonts, render to an image. `command()` is an explicit low-level escape hatch
for a single ASCII command. Caller-supplied raw TSPL files are sent unchanged.
This is API design compatibility, not a drop-in replacement for Brother's binary
protocol, model names or fixed label catalog.

## Serial transport and results

Bitmap bytes may contain XON/XOFF control bytes. Software flow control is therefore
not exposed; use a correctly wired hardware handshake when supported. No automatic
job retry occurs after errors, to avoid duplicate labels or completing a partial
command with the wrong bytes. A failed `Printer` session must be closed and reopened.

A successful result contains `instructions_sent=True`, `outcome="sent"`,
`bytes_sent`, `did_print=False`, `ready_for_next_job=False`, `printer_state=None`.
Here `False` means **not confirmed**, not proof that nothing printed. This release
waits for writes and the host's output queue to drain; that does not prove that
an adapter or printer received the data, or that a physical label printed.
`blocking=False` is not implemented. No completion/status query is claimed.

`PrintError.result` retains known progress. Its `outcome="unknown"` means a partial
job may have reached the device. `bytes_sent` counts acknowledged host write calls;
a failed write can have transmitted additional bytes before raising. JSON-mode
runtime failures exit 1; argument errors use Click stderr and exit 2.

A 600 × 360 bitmap is 27,000 bytes, taking at least about 28 seconds over 9600 baud
8N1, plus commands. Increase `--timeout` for larger jobs. If output is blank,
garbled or truncated, verify baud/parity/stop bits, RS-232 cable wiring and hardware
flow control, label/ribbon setup and TSPL mode before resending. Record measured
results in [docs/HARDWARE_TESTING.md](docs/HARDWARE_TESTING.md).

## Development

```sh
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
ruff format --check src tests
python -m build
```

Tests use synthetic images and fake serial ports; they never print a label.

## References

- [brother_ql](https://github.com/pklaus/brother_ql): API/CLI design reference; no implementation code copied.
- [pyniim](https://github.com/buganini/pyniim): convenience API and result conventions; local checkout reviewed.
- [tsclib](https://pypi.org/project/tsclib/): native TSPL operations reference; this project does not wrap its Windows DLL.
- [TSC downloads](https://usca.tscprinters.com/en/downloads): TSPL/TSPL2 programming manuals.
- [TSC TSPL/TSPL2 manual, mirrored PDF](https://manuals.plus/m/f21e1cc8c532dfa7d3838ac4677bfd4b438f37282bd5460b0292b179a72fdec7_optim.pdf): BITMAP width in bytes, height in dots and mode 0 overwrite.
- [TSC TTP-243/342 specification sheet, mirrored PDF](https://autoid.com.hk/pos/labelprinter/tsc/ttp-243.pdf): TTP-342 12 dots/mm profile basis; does not establish elitek firmware compatibility.
- [pyserial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html): serial parameters and transport behavior.

## macOS / Linux: CUPS USB printing

USB-to-IEEE-1284 adapters are CUPS printer devices, not serial ports. Use the
`cups` backend on macOS or Linux with CUPS client tools (`lp`, `lpstat`, `lpinfo`).
Windows print queues are not supported. No Python CUPS extension is required.

```sh
pytsc -b cups discover --json
```

Discovery lists configured queues (`cups://QUEUE`, `kind=queue`, `printable=true`)
and unconfigured device URIs (`kind=device`, `printable=false`). `printable` means
a queue exists, not that the printer is online/accepting jobs or TSPL-compatible.
If device discovery requires privileges, is unavailable or times out, queue results
remain visible with a warning record. Discovery never creates a queue or prints.

For the reported device `usb://Unknown/IEEE-1284%20Controller?location=1140000`,
you can print directly (queue setup is automatic when permitted):

```sh
pytsc -b cups -p 'usb://Unknown/IEEE-1284%20Controller?location=1140000' \
  print -l 50x30 --gap 2 --dither examples/test-label.png
```

Alternatively, manually create a queue on CUPS versions supporting raw queues:

```sh
sudo lpadmin -p TTP342 -E -v 'usb://Unknown/IEEE-1284%20Controller?location=1140000' -m raw
pytsc -b cups -m TTP-342 -p TTP342 print -l 50x30 --gap 2 --dither examples/test-label.png
# Equivalently: -p cups://TTP342
```

Before each CUPS print/send, pytsc now **deletes and recreates the target USB queue
by default**, as intended for this exclusively used printer. This discards all
pending jobs and custom settings in that queue. An existing queue keeps its name;
a new USB URI uses `pytsc_<URI hash>`. The resulting device URI is verified.
Use the global `--no-recreate-cups-queue` option to retain and reuse the queue:

```sh
pytsc --no-recreate-cups-queue -p 'cups://TTP342' send /tmp/test.tspl
```

Python callers can pass `recreate_queue=False` to `Printer` or `send`. The default
is `True`. Named queues must target USB for automatic recreation; other CUPS
transports require opting out. Queue deletion/creation failures stop submission.
Discovery and status never recreate queues. Recreation resets CUPS configuration,
not necessarily a stalled USB endpoint; hardware reliability remains unverified.
On macOS it uses the system Generic PostScript PPD (`lpadmin -P`), because macOS
rejects `-m raw`. TSPL jobs still use `lp -o raw` to bypass PPD rendering; this does
not make the printer PostScript-compatible. Do not use the generic queue for normal
macOS document printing. Linux currently uses `-m raw`.
It never invokes sudo automatically. Permission errors include the exact setup
command; unsupported raw queues require system printer configuration.
Raw queues are deprecated in newer CUPS; if your version rejects them, configure
a suitable queue using system printer settings and verify it accepts raw TSPL.
The device URI can change when moving USB ports. `-p` accepts a queue name, `cups://QUEUE`, or an encoded `usb://` URI. Baud rate and serial handshaking do not apply to CUPS.

Submission uses `lp -d QUEUE -n 1 -o raw -o job-sheets=none,none -- -`, passing
TSPL bytes on stdin without shell interpretation or document conversion. Copies
are encoded in TSPL, so CUPS is always asked to spool one copy. Results report
`outcome="queued"` and `job_id` when available; queue acceptance does not confirm
printer receipt or physical printing. On a submission timeout/failure, inspect
`lpstat -o QUEUE` before retrying. `--timeout` limits submission, not printing.

Python: `Printer("TTP342", backend="cups")`, or
`send(data, "TTP342", backend_identifier="cups")`. Serial-specific keyword
arguments are not accepted by the CUPS API.

`pytsc discover` and Python `discover()` scan both serial and CUPS by default.
Each record includes its `backend`; failures of one backend appear as warnings
without discarding results from the other. Explicit `-b` or `PYTSC_BACKEND` restricts
the CLI scan. Printing automatically selects CUPS for `usb://` and `cups://` identifiers,
and serial otherwise. Bare CUPS queue names require `-b cups`. Explicit `-b` or
`PYTSC_BACKEND` takes precedence over inference. Python `Printer` and `send()`
use the same inference when no backend is provided.
Discovery never creates queues. USB queue resolution/recreation happens only when
sending a nonempty job; no print job is submitted if setup or verification fails.

## Troubleshooting stalled CUPS jobs

```sh
pytsc -p 'usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000' status
# Or: pytsc -b cups -p QUEUE status --json
```

This reads queue state, acceptance and pending jobs without modifying the queue.
A successful submission can remain queued after a USB transmission error.
CUPS's default `stop-printer` error policy can disable a queue after a failed job;
new pytsc-created queues use `printer-error-policy=abort-job` instead. This aborts
the failed job without automatically replaying it or stopping later jobs. It does
not fix USB communication failures or guarantee that partially sent data was cleared.
When recreation is disabled, existing queues retain their policy; to update one explicitly:

```sh
lpadmin -p QUEUE -o printer-error-policy=abort-job
```

When a queue is disabled, inspect its pending jobs before enabling it. Cancel only
a job you intend to discard with `cancel QUEUE-JOBNUMBER`; clear any incomplete
printer command using the printer's documented procedure, then run `cupsenable QUEUE`.
Enabling can release pending jobs, so do not blindly enable or resubmit repeatedly.
Deleting and recreating the printer is usually unnecessary for a disabled queue.
If USB transport errors recur, check adapter/cable reliability and printer status;
the error policy is a recovery improvement, not a confirmed transport fix.

### Diagnosing skewed large bitmaps

For a 100 × 60 mm label at 12 dots/mm, the image is 1200 × 720 dots:
150 bytes per row, 108,000 payload bytes. If rows shift progressively, compare the
preview with the printed label and check physical label dimensions, printer
resolution and transport errors. A diagnostic option can split the same pixels
into multiple BITMAP commands at successive Y coordinates:

```sh
pytsc -p 'usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000' \
  print -l 100x60 --fit contain --gap 2 --dither --bitmap-rows 128 examples/test-label.png
```

`--bitmap-rows 0` (default) sends one BITMAP per image. A value of 128 produces six
strips for this example, each at most 19,200 bytes, followed by a single PRINT.
This is a diagnostic comparison, not a verified firmware workaround. It does not
pace USB transfers, reduce total image memory, or fix an incorrect row width.

## ASCII BAR image encoding

`--raster-mode bar` renders the same monochrome pixels using ASCII `BAR` commands
instead of binary `BITMAP`. Identical horizontal black runs are merged vertically
to reduce command count. Image preparation, rotation, scaling, threshold and
Floyd–Steinberg dithering are unchanged. Bitmap remains the default.

```sh
pytsc -p 'usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000' \
  print -l 102x76.2 --gap 3 --fit contain --dither --raster-mode bar examples/test-label.png
```

Python: `convert(..., raster_mode="bar")` or
`printer.print_image(..., raster_mode="bar")`. Low-level `TSPLRaster.bars(image)`
accepts mode-1 images and optional x/y coordinates; white pixels are transparent,
so clear the label first. The conversion API clears it automatically.
`--bitmap-rows` must remain 0 for BAR mode.

This is an experimental alternative for diagnosing binary-data corruption, not a
verified USB fix. Dithered images can generate many commands and larger files; the
full 102 × 76.2 mm test image produces approximately 392 KB of ASCII commands.
No automatic pacing/retry is added. Offline tests reconstruct all BAR rectangles
and compare every pixel against the prepared image.

## Experimental direct USB (PL2305 only)

Install `python -m pip install -e '.[usb]'` and system libusb (on macOS, Homebrew
`libusb`). This optional backend targets only VID:PID `067b:2305`. It claims the
printer-class **unidirectional** alternate setting and bulk OUT endpoint, skips
soft reset by default, and uses 512-byte writes with a 10 ms gap. These are experimental transport settings, not measured printer limits.

```sh
pytsc -b pyusb discover --json
pytsc -p pyusb://067b:2305 --timeout 20 send examples/diagnostics/d-bar-bitmap.tspl
```

Use `pyusb://067b:2305/BUS/ADDRESS` if multiple adapters are attached. USB bus/address
may change on reconnection. Existing `usb://...` identifiers still mean CUPS;
`pyusb://...` selects direct access. Default discovery includes optional pyusb and
reports missing dependencies as a warning without suppressing other backends.

Global options: `--usb-chunk-size`, `--usb-write-delay-ms`, and
`--usb-soft-reset/--no-usb-soft-reset`. Python `send`/`Printer` accept `chunk_size`,
`write_delay` (seconds), and `soft_reset=False` with backend `pyusb`. Stop/cancel CUPS jobs
for this device before direct access. The backend does not delete queues, detach
system drivers, replay failed bytes, or perform a whole-device reset.

The upstream PL2305 quirk inspired this transport, but its reset behavior is
**not implemented identically**. Reset is opt-in with `--usb-soft-reset`; it runs
before sending, never immediately afterward. The tested adapter rejected soft
reset and clear-halt with Pipe error, so leave reset disabled on this setup.
Partial writes are handled; errors report known acknowledged bytes and invalidate
the session. `sent` means USB writes completed, not physical printing.

With reset disabled, user-confirmed output includes two consecutive matching
native/BITMAP comparison labels and one full dithered test image. This validates
the tested path, but does not isolate whether unidirectional mode, pacing, or
bypassing CUPS resolved the earlier corruption.
