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


def discover(backend_identifier=None):
    """Scan all backends by default; preserve partial results with warnings."""
    scanners = {"serial": discover_serial, "cups": discover_cups}
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


def send(instructions, printer_identifier, backend_identifier="serial", blocking=True, **options):
    """Wait for transport submission, not confirmed physical printing."""
    if not blocking:
        raise ValueError("Background sending is not implemented")
    backend = open_backend(printer_identifier, backend_identifier, **options)
    try:
        return backend.send(instructions)
    finally:
        backend.close()
