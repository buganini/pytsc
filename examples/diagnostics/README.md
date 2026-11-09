# Equal-payload width comparison

Both TSPL files use 100 × 60 mm stock, a 2 mm gap, one copy, and one BITMAP
command with exactly 54,000 raster bytes. They use different image dimensions:

| Test | Image | Bytes per row | Height |
| --- | --- | --- | --- |
| A: narrow/tall | 600 × 720 dots (50 × 60 mm) | 75 | 720 |
| B: wide/short | 1200 × 360 dots (100 × 30 mm) | 150 | 360 |

The PNGs show the bitmap only. The narrow bitmap leaves half the label width
blank; the short bitmap leaves half the label length blank. Native label settings
remain identical, so paper size and feed settings are not changed between tests.
Grayscale patches use Floyd–Steinberg dithering. No scaling or splitting occurs
when sending these files; do not run them through `print --fit contain`.

```sh
pytsc -p 'usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000' send examples/diagnostics/a-narrow.tspl
# Wait for A, check output and queue state, then send B:
pytsc -p 'usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000' send examples/diagnostics/b-wide.tspl
```

If only B fails, investigate width-dependent bitmap handling. If both fail,
transport or other firmware behavior remains possible. These tests do not by
themselves establish a root cause. Each send physically prints one label.
