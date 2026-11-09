"""CUPS command-line transport for macOS/Linux; raw jobs bypass document filters."""

import math
import os
import re
import subprocess

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


def discover():
    """List queues and unconfigured devices. Partial discovery reports warnings."""
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


class CUPSBackend:
    def __init__(self, identifier, *, timeout=120):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("A CUPS queue name or cups://QUEUE is required")
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
        result = dict(
            instructions_sent=False,
            outcome="unknown",
            bytes_sent=0,
            did_print=False,
            ready_for_next_job=False,
            printer_state=None,
            job_id=None,
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
