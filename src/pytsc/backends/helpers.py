from .cups import CUPSBackend
from .cups import discover as discover_cups
from .pyusb import USBBackend
from .pyusb import discover as discover_usb
from .serial import SerialBackend
from .serial import discover as discover_serial


def resolve_backend(identifier, backend_identifier=None):
    """Explicit selection wins; recognize CUPS URI schemes, otherwise use serial."""
    if backend_identifier is not None:
        if backend_identifier not in ("serial", "cups", "pyusb"):
            raise ValueError(f"Unknown backend: {backend_identifier}")
        return backend_identifier
    if isinstance(identifier, str) and identifier.startswith("pyusb://"):
        return "pyusb"
    return (
        "cups"
        if isinstance(identifier, str) and identifier.startswith(("usb://", "cups://"))
        else "serial"
    )


def open_backend(identifier, backend_identifier=None, **options):
    backend_identifier = resolve_backend(identifier, backend_identifier)
    if backend_identifier == "pyusb":
        return USBBackend(identifier, **options)
    if backend_identifier == "serial":
        return SerialBackend(identifier, **options)
    if backend_identifier == "cups":
        return CUPSBackend(identifier, **options)
    raise ValueError(f"Unknown backend: {backend_identifier}")


def discover(backend_identifier=None):
    """Scan all backends by default; preserve partial results with warnings."""
    scanners = {"serial": discover_serial, "cups": discover_cups, "pyusb": discover_usb}
    if backend_identifier is not None and backend_identifier not in scanners:
        raise ValueError(f"Unknown backend: {backend_identifier}")
    records = []
    for name in [backend_identifier] if backend_identifier else scanners:
        try:
            records.extend({**row, "backend": name} for row in scanners[name]())
        except (RuntimeError, OSError) as exc:
            if backend_identifier:
                raise
            records.append({"kind": "warning", "backend": name, "message": str(exc)})
    return records


def send(instructions, printer_identifier, backend_identifier=None, blocking=True, **options):
    """Wait for transport submission, not confirmed physical printing."""
    if not blocking:
        raise ValueError("Background sending is not implemented")
    backend = open_backend(printer_identifier, backend_identifier, **options)
    try:
        return backend.send(instructions)
    finally:
        backend.close()
