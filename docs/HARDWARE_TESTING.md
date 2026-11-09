# Hardware testing

No physical printing has been verified. Target: elitek TTP-342 via RS-232/USB adapter.
Software tests alone do not establish device compatibility.

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
