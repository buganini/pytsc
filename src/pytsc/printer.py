from .backends.serial import SerialBackend
from .conversion import convert
from .raster import TSPLRaster


class Printer:
    """Reusable serial session. Prefer a with statement to close reliably."""

    def __init__(self, identifier, model="TTP-342", **serial_options):
        self.raster = TSPLRaster(model)
        self.identifier = identifier
        self.serial_options = serial_options
        self.backend = None

    def open(self):
        if self.backend is None:
            self.backend = SerialBackend(self.identifier, **self.serial_options)
        return self

    def close(self):
        if self.backend is not None:
            self.backend.close()
            self.backend = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def send(self, instructions):
        if self.backend is None:
            raise RuntimeError("Open the printer with a context manager or open() first")
        return self.backend.send(instructions)

    def print_image(self, image, label, **options):
        instructions = convert(self.raster, [image], label, **options)
        return self.send(instructions)
