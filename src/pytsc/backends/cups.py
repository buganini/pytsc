"""CUPS command-line transport for macOS/Linux; raw jobs bypass document filters."""

import hashlib
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from ..errors import PrintError


def _run(arguments, *, timeout=15, data=None):
    try:
        return subprocess.run(
            arguments,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"CUPS command {arguments[0]!r} is unavailable; install CUPS client tools"
        ) from exc


def _queues():
    """Read queues without triggering slow device discovery."""
    records = []
    try:
        queues = _run(["lpstat", "-v"])
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("CUPS queue discovery timed out") from exc
    output = queues.stdout.decode(errors="replace")
    error = queues.stderr.decode(errors="replace").strip()
    if queues.returncode and "No destinations added" not in output + error:
        raise RuntimeError(f"CUPS queue discovery failed: {error or output}")
    known = set()
    for line in output.splitlines():
        match = re.match(r"device for (.+?): (.+)$", line)
        if match:
            name, uri = match.groups()
            known.add(uri)
            records.append(
                dict(
                    identifier=f"cups://{name}",
                    queue=name,
                    device_uri=uri,
                    kind="queue",
                    printable=True,
                )
            )
    return records


def discover():
    """List queues and unconfigured devices. Partial discovery reports warnings."""
    records = _queues()
    known = {row["device_uri"] for row in records}
    try:
        devices = _run(["lpinfo", "-v"], timeout=20)
        if devices.returncode:
            raise RuntimeError(devices.stderr.decode(errors="replace").strip() or "lpinfo failed")
        for line in devices.stdout.decode(errors="replace").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and "://" in parts[1] and parts[1] not in known:
                known.add(parts[1])
                records.append(
                    dict(
                        identifier=parts[1],
                        device_uri=parts[1],
                        kind="device",
                        printable=False,
                        connection=parts[0],
                    )
                )
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        records.append(dict(kind="warning", message=f"Device discovery unavailable: {exc}"))
    return records


MACOS_GENERIC_PPD = Path(
    "/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/"
    "PrintCore.framework/Versions/A/Resources/Generic.ppd"
)


def _queue_driver_options():
    # macOS rejects `-m raw` at queue creation. A PPD-backed queue still accepts
    # per-job `lp -o raw`; the PPD is not used to render our TSPL payload.
    if sys.platform == "darwin":
        if not MACOS_GENERIC_PPD.is_file():
            raise RuntimeError(
                "macOS Generic.ppd is unavailable; configure a CUPS queue in system settings "
                "and pass its name with -b cups. No queue or print job was created."
            )
        return ["-P", str(MACOS_GENERIC_PPD)]
    return ["-m", "raw"]


def _resolve_usb(uri):
    queues = _queues()
    matches = sorted(row["queue"] for row in queues if row["device_uri"] == uri)
    if matches:
        return matches[0]
    queue = "pytsc_" + hashlib.sha256(uri.encode()).hexdigest()[:16]
    if any(row["queue"].lower() == queue.lower() for row in queues):
        raise RuntimeError(f"CUPS queue name collision: {queue}; existing queue was not modified")
    command = ["lpadmin", "-p", queue, "-E", "-v", uri, *_queue_driver_options()]
    try:
        response = _run(command)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "CUPS queue creation timed out; check lpstat -v before retrying"
        ) from exc
    if response.returncode:
        message = response.stderr.decode(errors="replace").strip()
        permission_error = any(
            token in message.lower()
            for token in (
                "forbidden",
                "not authorized",
                "unauthorized",
                "permission",
                "not permitted",
                "authentication",
            )
        )
        advice = (
            " Administrator permission is required; run: " + shlex.join(["sudo", *command])
            if permission_error
            else " Configure a compatible CUPS queue in system settings and pass its name with -b cups."
        )
        raise RuntimeError(f"Cannot create CUPS queue: {message}." + advice)
    if not any(row["queue"] == queue and row["device_uri"] == uri for row in _queues()):
        raise RuntimeError("Created CUPS queue could not be verified; no print job submitted")
    return queue


class CUPSBackend:
    def __init__(self, identifier, *, timeout=120):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("A CUPS queue name or cups://QUEUE is required")
        self.device_uri = None
        if identifier.startswith("usb://"):
            parsed = urlsplit(identifier)
            if (
                not parsed.netloc
                or not parsed.path
                or parsed.fragment
                or any(c.isspace() or ord(c) < 32 for c in identifier)
            ):
                raise ValueError("Invalid USB URI; use the encoded URI returned by discover")
            self.device_uri = identifier
            self.queue = None
            self.timeout = timeout
            return
        queue = identifier.removeprefix("cups://")
        if not queue or any(c.isspace() or ord(c) < 32 or c in "/#" for c in queue):
            raise ValueError(
                "Use a CUPS queue name or cups://QUEUE, not a USB device URI; create a queue first"
            )
        self.queue = queue
        self.timeout = timeout

    def send(self, data):
        if not isinstance(data, bytes) or not data:
            raise ValueError("Instructions must be nonempty bytes")
        if self.device_uri:
            self.queue = _resolve_usb(self.device_uri)
        result = dict(
            instructions_sent=False,
            outcome="unknown",
            bytes_sent=0,
            did_print=False,
            ready_for_next_job=False,
            printer_state=None,
            job_id=None,
            queue=self.queue,
        )
        try:
            process = _run(
                [
                    "lp",
                    "-d",
                    self.queue,
                    "-n",
                    "1",
                    "-o",
                    "raw",
                    "-o",
                    "job-sheets=none,none",
                    "-t",
                    "pytsc TSPL",
                    "--",
                    "-",
                ],
                timeout=self.timeout,
                data=data,
            )
        except subprocess.TimeoutExpired as exc:
            raise PrintError(
                "CUPS submission timed out; the job may have been accepted. Check lpstat before retrying",
                result,
            ) from exc
        if process.returncode:
            message = process.stderr.decode(errors="replace").strip()
            raise PrintError(
                f"CUPS submission failed: {message}; check the queue before retrying", result
            )
        output = process.stdout.decode(errors="replace")
        match = re.search(r"request id is (\S+)", output)
        result.update(
            instructions_sent=True,
            outcome="queued",
            bytes_sent=len(data),
            job_id=match.group(1) if match else None,
        )
        return result

    def close(self):
        """No persistent connection: each send submits one CUPS job."""
