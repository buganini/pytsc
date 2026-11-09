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
