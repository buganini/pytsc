# Hardware testing

Physical output has been reported on an elitek TTP-342 through macOS CUPS and a
Prolific USB-to-IEEE-1284 adapter. This is **not a full hardware qualification**:
large bitmap corruption and intermittent transport failures remain unresolved.
Serial transport has not been tested on this device.

Use `examples/test-label.png` and the README CLI instructions. No Python example
script is required. The supplied image is 50 × 30 mm at 12 dots/mm.

For the first run, record:

- Printer branding/model, firmware/self-test sheet and TSPL language mode.
- OS, adapter model/chipset, device path and RS-232 cable wiring.
- Baud rate, 8 data bits, parity, stop bits and flow control matching the printer.
- Label width × feed length, gap/black mark, thermal transfer ribbon or direct thermal.
- Exact CLI command, transmitted bytes, elapsed time, and photo of output.
- 10 mm square dimensions, top/left/right orientation, smallest visible line,
  black/white polarity, clipping and feed alignment.

Then verify multiple copies/pages, black mark or continuous stock if needed, and
out-of-paper/disconnect behavior. Transmission success is not print completion.
Do not blindly retry after a partial transmission: clear the incomplete job using
the printer's documented procedure before sending another job.

## 2026-11-09: initial macOS CUPS investigation

- Connection: `usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000`.
- Queue: `pytsc_a5def079ff41fc89`, system Generic PPD; jobs submitted with `lp -o raw`.
- Media: user reports 4 × 3 inch stock, approximately 3 mm gap. Existing Windows
  layout shows paper 102 × 76.2 mm, template 99.5 × 76.2 mm, approximately 1.3 mm
  left/right margins. Current diagnostic setting is 102 × 76.2 mm, gap 3 mm.
- Initial 50 × 30 mm test produced physical output; user observed monochrome
  rendering. Dithering was enabled in subsequent examples.
- Enlarged images show horizontal fragmentation and repeated displaced pieces.
  Splitting BITMAP into 128-row strips did not resolve the photographed problem.
- After correcting paper settings, a later photograph shows the header and arrow
  aligned, with corruption starting farther down the bitmap. This suggests that
  alignment can be lost mid-image; it does not establish a transport/firmware cause.
- A narrow/tall 600 × 720 bitmap (job 19, 54,000 bitmap bytes) produced faint,
  incomplete output. At that point its paper setting was still 100 × 60 mm, gap
  2 mm; its apparent cross-label placement cannot isolate bitmap behavior.
- The wide/short comparison (job 20) reported offline and was canceled. A/B width
  comparison therefore remains inconclusive.
- CUPS logged `Unable to send data to printer` for jobs 3 and 11; later log details
  show USB backend failure for job 16. Jobs 18 and 20 reported offline and were
  canceled. Restarting the printer allowed the next submission but did not establish
  reliable consecutive printing. The adapter and URI remained discoverable.
- Queue error policy was changed to `abort-job`, without automatic resubmission.
  This is recovery behavior, not a verified fix for the USB failures.
- Native TEXT/BOX/BAR test prepared as `examples/diagnostics/c-native.tspl`:
  661 bytes, one label, no bitmap. Job 23 reported offline and was canceled.
  No visual result was obtained. Retry only after the user resets the device,
  with this test first rather than after a bitmap job.

Firmware version, measured printhead resolution, actual media calibration, print
speed and thermal media/ribbon configuration are not yet recorded. Keep
`hardware_verified=False` until basic geometry and repeatability are validated.

### Native control photo and small-bitmap comparison

After restarting the printer, the user sent C and supplied a photo. All four text
rows and the three vertical bars appear in their expected relative positions,
without the earlier horizontal fragmentation. Horizontal BOX edges are faint or
missing, so print quality is not validated. This supports working basic native
command interpretation but does not validate bulk binary transfer.

D compares identical native BAR and 240 × 240 dot BITMAP patterns on one label.
BITMAP payload is 7,200 bytes; the entire job is 7,787 bytes. Prepared and submitted
as job 25. CUPS USB backend failed before reporting any bytes sent:

- `CONTENT_TYPE=application/vnd.cups-raw`: raw submission reached the backend.
- `Read 7787 bytes of print data...`
- `Got USB pipe stalled during write`
- `USB class driver WritePipe returned e000404f`
- `Sent 0 bytes...`

This is evidence of a USB transport stall for job 25, not a bitmap rendering
result. It does not establish why earlier partially corrupted labels occurred.
The job is no longer pending and was not automatically resent. Next isolate USB
adapter state by unplugging/reconnecting it before retrying D as the first job.

### Small BITMAP visual success

The user subsequently supplied a D photo with matching native BAR and BITMAP
patterns: horizontal/vertical geometry, square position and polarity agree.
Small breaks are visible in the native pattern. This establishes successful
240 × 240 dot / 7,200-byte BITMAP rendering in that run, not reliable USB transport
or compatibility with larger images. The exact reset sequence was not recorded.

Prepared E480/E720: fixed 240-dot width and increased heights, with 14,400/21,600
bitmap bytes. Before sending these, repeated D as job 28 to isolate consecutive-job
behavior from increasing payload size.
Job 28 reported `The printer is offline` and remained pending. It was canceled;
E480/E720 were not sent. The same small job can therefore fail on a subsequent
attempt without increasing bitmap dimensions or bytes. This is evidence of an
independent connection-state/repeatability issue, not proof of its underlying cause.


### Exclusive queue recreation mode

At the user's request, CUPS submission now defaults to deleting and recreating the
target USB queue before each job. Pending jobs/custom settings are discarded.
`--no-recreate-cups-queue` / `recreate_queue=False` retains the old reuse behavior.
This is an explicitly requested recovery experiment; no successful repeated-job
hardware evidence has yet established that recreation fixes endpoint stalls or
bitmap corruption. Serial, discovery and status operations are unaffected.

### ASCII raster alternative

Subsequent user photos of the same D test show its native BAR pattern largely
stable while the 7,200-byte BITMAP changes shape between attempts/resets. This
makes a deterministic width-only explanation insufficient. Windows comparison
is unavailable. Neither binary transport nor firmware parsing has been isolated.

Implemented optional ASCII BAR raster encoding with vertical run merging. The
full dithered test image at 102 × 76.2 mm, gap 3 mm, yields 392,232 total bytes.
Offline rectangle reconstruction matches every prepared image pixel. Submitted
one copy as job 31. Despite recreating the queue, CUPS logged USB pipe stalled
during write and `Sent 0 bytes`; the job left the queue with a transport error.
No BAR-image hardware result was obtained and no retry was performed. This mode
is not claimed to repair the underlying USB endpoint stalls.

### Upstream implementation review

- OpenPrinting's USB quirk table explicitly lists PL2305 `067b:2305` with
  `no-reattach soft-reset unidir`:
  https://github.com/OpenPrinting/cups/blob/master/backend/org.cups.usb-quirks
- Its linked historical bug describes successful first printing followed by
  non-response until power cycling (Linux, HP 4L; not proof for our TSC/macOS case):
  https://bugs.launchpad.net/ubuntu/+source/cups/+bug/987485
- Apple's reviewed `usb-darwin.c` opens the printer class driver in bidirectional
  mode first, falling back to unidirectional only if opening fails. Its URI parser
  handles waiteof, serial and location, not the Linux quirk table. Do not assume
  adding a Linux usb-quirks file or a made-up unidir URI parameter affects macOS:
  https://github.com/apple/cups/blob/master/backend/usb-darwin.c
- RayforLoy/TSC-Printer uses TSCLIB.dll `sendcommand` and works around NUL bytes
  by modifying the bitmap and drawing a second overlay. That string/DLL path is
  different from pytsc's byte-preserving subprocess stdin; do not copy the workaround
  without evidence of NUL truncation in this transport:
  https://github.com/RayforLoy/TSC-Printer/blob/master/bitmap.py
- cbiffle/raster-tspl-rs packs MSB-first rows, byte-width headers and unencoded
  binary payloads. Its Beeprt implementation uses mode 1 with inverted bits,
  unlike our overwrite mode 0. Its firmware-specific settings are not TTP-342
  support evidence:
  https://github.com/cbiffle/raster-tspl-rs/blob/main/src/main.rs

The PL2305 transport workaround is the strongest new lead. It motivates testing
unidirectional USB access and reset handling in a separately controlled backend,
not claiming a proven TSPL encoder defect or blindly changing macOS system drivers.


### Direct USB experiment

Canceled stalled CUPS job 35 before direct access. Device descriptors show:
configuration 1/interface 0/alternate 0 = printer class, protocol 1, OUT 0x01;
alternate 1 = protocol 2 with IN 0x82; alternate 2 is vendor-specific.
System libusb and pyusb successfully claimed the unidirectional alternate.
Sending D with pre-send soft reset failed with 0 acknowledged bytes. Follow-up
control-only probes confirmed both recipient 0x23 and 0x21 soft resets and
`clear_halt(0x01)` returned Pipe error. No payload was sent in this attempt.
No system drivers were detached or changed. Optional backend is experimental;
it does not yet establish a workaround for the adapter/connection fault.


### Successful direct USB output (2026-11-09)

With `--no-usb-soft-reset`, the user confirmed that `d-bar-bitmap.tspl` printed
matching native and bitmap grids, then repeated successfully without a restart
or reconnect. The full image command also produced a correctly arranged label:

```sh
pytsc -p pyusb://067b:2305 --timeout 20 --no-usb-soft-reset \
  print -l 102x76.2 --gap 3 --fit contain --dither examples/test-label.png
```

The photo shows no earlier bitmap fragmentation or row shifts. Some fine lines
remain faint; print quality and measured geometry are separate pending checks.
The source image's printed dimension captions are scaled along with the image,
so they are not measurements of the enlarged output.

Soft reset is now disabled by default in both CLI and Python backend, matching
these successful tests. Unidirectional mode, 512-byte writes and 10 ms pacing
remain unchanged. This does not establish which transport change was decisive,
and does not establish a fix for CUPS. The earlier failed reset experiment above
is retained as historical evidence.

Follow-up report (2026-11-09): the user confirmed that all four labels printed
normally. Suggested tests were repeated single-label printing, `--copies 2`, and
an optional 100 mm width comparison. The report did not enumerate the commands
actually run; do not infer specific width, copy-count, or no-restart coverage
from the total alone. This adds successful physical output evidence; no further
routine test batch is required before using the successful settings. The model's
`hardware_verified` flag remains false pending measured geometry and broader
repeatability checks.


The successful 102 mm width is a tested media setting, not a fixed printer width
or a requirement for correct bitmap output. A 100 mm width has not yet been
verified using this successful PyUSB path. Previous CUPS corruption does not
establish a width-dependent encoder or firmware fault.
