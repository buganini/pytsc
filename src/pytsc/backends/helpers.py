from .serial import SerialBackend
from .serial import discover as discover_serial


def discover(backend_identifier="serial"):
    if backend_identifier != "serial":
        raise ValueError("Only the serial backend is implemented")
    return discover_serial()


def send(
    instructions,
    printer_identifier,
    backend_identifier="serial",
    blocking=True,
    **options,
):
    """Wait for host transmission, not confirmed physical printing."""
    if backend_identifier != "serial":
        raise ValueError("Only the serial backend is implemented")
    if not blocking:
        raise ValueError("Background sending is not implemented")
    backend = SerialBackend(printer_identifier, **options)
    try:
        return backend.send(instructions)
    finally:
        backend.close()
