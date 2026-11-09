from .cups import CUPSBackend
from .cups import discover as discover_cups
from .serial import SerialBackend
from .serial import discover as discover_serial


def open_backend(identifier, backend_identifier="serial", **options):
    if backend_identifier == "serial":
        return SerialBackend(identifier, **options)
    if backend_identifier == "cups":
        return CUPSBackend(identifier, **options)
    raise ValueError(f"Unknown backend: {backend_identifier}")


def discover(backend_identifier="serial"):
    if backend_identifier == "serial":
        return discover_serial()
    if backend_identifier == "cups":
        return discover_cups()
    raise ValueError(f"Unknown backend: {backend_identifier}")


def send(instructions, printer_identifier, backend_identifier="serial", blocking=True, **options):
    """Wait for transport submission, not confirmed physical printing."""
    if not blocking:
        raise ValueError("Background sending is not implemented")
    backend = open_backend(printer_identifier, backend_identifier, **options)
    try:
        return backend.send(instructions)
    finally:
        backend.close()
