# Third-party sources and license review

Reviewed on 2026-11-10 against pytsc commit
`ac9c30ca51b7e0fef4ad090ce31b2b1df3d215ce` and its recorded history.
This is a targeted source-provenance review, not a legal opinion or a guarantee
that every possible source of similarity has been identified. Remote links below
refer to branches inspected on that date, not pinned historical snapshots.

## Findings

The comparison found no substantial copied implementation from brother_ql,
raster-tspl-rs, or the reviewed CUPS sources in the inspected pytsc code. Shared
interface names, result keys, protocol constants, command syntax and common
library calls are present and intentional. This finding supports retaining MIT
for the project's own code; it does not relicense any upstream material.

The Git history starts with the TSPL implementation in `3480eb1`. The recorded
CUPS/TSPL implementation comparison was added in `4d44084`, followed by the
PyUSB backend in `b880d4f`. History records these changes, but is not by itself
proof of independent authorship. The review also compared the actual conversion,
raster, CLI, transport helper and USB reset implementations.

No upstream driver source, vendor DLL, CUPS PPD, original manual PDF or upstream
model catalog is tracked in this repository. The CUPS backend invokes installed
command-line tools and references the system Generic.ppd; it does not bundle
Apple's USB backend or that PPD. Test images and diagnostic jobs were generated
for this project during development; the image-generation script was not retained.
This review did not audit the license provenance of the fonts used in those images.

## Sources used during development

| Source | License evidence | Use and review finding |
| --- | --- | --- |
| [brother_ql](https://github.com/pklaus/brother_ql) | [GPL v3 text](https://github.com/pklaus/brother_ql/blob/master/LICENSE); [package metadata](https://github.com/pklaus/brother_ql/blob/master/setup.py) identifies GPLv3-or-later | API/CLI organization, common option meanings, result keys and threshold convention. Compared `cli.py`, `conversion.py` and `backends/helpers.py`; no substantial implementation copy identified. |
| [pyniim](https://github.com/buganini/pyniim) | MIT, checked in local checkout at `a2790fcdabef823c8f3e6ebe9dfb1416f6eeefb2` | Convenience API, image handling and result conventions. Same copyright holder, Buganini Chiu. Its BLE protocol, model catalog and bundled upstream model data are not incorporated into pytsc. |
| [raster-tspl-rs](https://github.com/cbiffle/raster-tspl-rs) | MPL-2.0, including the header of [src/main.rs](https://github.com/cbiffle/raster-tspl-rs/blob/main/src/main.rs) | Compared bitmap layout and command framing. Its CUPS raster/PPD processing and Rust packing implementation are not included or translated into pytsc. |
| [OpenPrinting CUPS](https://github.com/OpenPrinting/cups) | [Apache-2.0](https://github.com/OpenPrinting/cups/blob/master/LICENSE), with [CUPS exceptions and notices](https://github.com/OpenPrinting/cups/blob/master/NOTICE); `usb-libusb.c` carries an Apache-2.0 header | PL2305 quirk research and USB reset behavior informed the Python backend. No CUPS source or quirk database is bundled. |
| [Apple CUPS usb-darwin.c](https://github.com/apple/cups/blob/master/backend/usb-darwin.c) | File-specific Apple permission notice in its header; do not describe this file solely by the repository's Apache-2.0 LICENSE | Read to diagnose macOS USB mode selection, URI handling and stalls. No implementation from this file identified in pytsc. |
| [tsclib](https://pypi.org/project/tsclib/) | Python project declares MIT; this does not establish the license of the included TSC DLL | API reference only. No dependency, DLL or wrapper code incorporated. |
| [RayforLoy/TSC-Printer](https://github.com/RayforLoy/TSC-Printer) | No explicit repository license found in the reviewed listing | Examined `bitmap.py` while investigating binary corruption. Its DLL/NUL-byte overlay workaround was not adopted; no code or DLL incorporated. |
| TSC TSPL manuals and TTP-342 specifications | Vendor documents; no open-source license established | Command syntax and device specifications only. Links are in the README; original documents are not bundled. |

### Implementation distinctions

- `conversion.py` uses Pillow RGBA composition, EXIF handling and optional padding,
  with separate image preparation and atomic replacement of TSPL output.
  brother_ql's Brother initialization, tape offsets, two-color conversion and
  response-processing implementation are absent.
- `raster.py` uses Pillow's packed mode-1 bytes with explicit white padding and
  TSPL overwrite mode 0. The reviewed Rust filter packs grayscale pixels itself,
  inverts the packed bytes and emits mode 1. Shared TSPL headers and row-width
  arithmetic describe the protocol; the implementation paths differ.
- `backends/pyusb.py` deliberately follows CUPS's OTHER-then-INTERFACE reset
  recipient order. The Python code retries only a PIPE error, optionally resets
  before transmission, and clears its OUT endpoint. CUPS's reviewed function
  resolves its interface through configuration descriptors and falls back after
  any negative transfer result. The protocol sequence is acknowledged as a
  research influence, not presented as an invention by pytsc.
- `backends/cups.py` manages queues and submits bytes through subprocess calls.
  It does not implement Apple's IOKit transport or port it to Python.

## Runtime dependencies

These are installed separately, not vendored in pytsc's wheel or source tree.
The versions below describe the environment inspected, not dependency pins.

| Component | Inspected license | Evidence |
| --- | --- | --- |
| Pillow 13.0.0 | MIT-CMU | Installed package metadata |
| Click 8.5.1 | BSD-3-Clause | Installed package metadata |
| pyserial 3.5 | BSD-3-Clause | Installed metadata and [upstream LICENSE.txt](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt) |
| PyUSB 1.3.1, optional | BSD-3-Clause | Installed distribution LICENSE |
| System libusb, used by PyUSB | LGPL v2.1 license text | [COPYING](https://github.com/libusb/libusb/blob/master/COPYING); not shipped by pytsc |
| System CUPS tools, optional | Version/file-specific CUPS terms | Installed separately; repository and file-specific distinctions noted above |

A distribution that bundles dependencies or system binaries needs to retain their
applicable notices and satisfy their own terms. The MIT declaration in pytsc's
metadata applies to pytsc, not to those separately licensed components.

## Maintenance

Preserve this distinction between reference material and incorporated code.
Before importing or porting upstream implementation, check that specific file's
license, record its revision and origin, and retain the required notices. Do not
assume a root license overrides a different file header, or that a publicly
readable repository without a license grants permission to reuse its code.
