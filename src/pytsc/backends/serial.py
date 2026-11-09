"""Raw serial transport for TSPL; successful writes do not confirm printing."""

import math
import time

import serial
from serial.tools import list_ports

from ..errors import PrintError


def discover():
    return [
        dict(identifier=p.device, description=p.description, hwid=p.hwid)
        for p in list_ports.comports()
    ]


class SerialBackend:
    def __init__(
        self,
        identifier,
        *,
        baudrate=9600,
        parity="N",
        stopbits=1,
        flow_control="none",
        timeout=120,
    ):
        if not identifier:
            raise ValueError("A serial device path or COM port is required")
        if flow_control not in ("none", "rtscts", "dsrdtr"):
            raise ValueError(
                "flow_control must be none, rtscts or dsrdtr; XON/XOFF is unsafe for raw bitmaps"
            )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if type(baudrate) is not int or baudrate <= 0:
            raise ValueError("baudrate must be a positive integer")
        self.timeout = timeout
        self.port = serial.Serial(
            port=identifier.removeprefix("serial://"),
            baudrate=baudrate,
            bytesize=8,
            parity=parity,
            stopbits=stopbits,
            timeout=min(timeout, 2),
            write_timeout=timeout,
            rtscts=flow_control == "rtscts",
            dsrdtr=flow_control == "dsrdtr",
            xonxoff=False,
        )
        self.failed = False

    def send(self, data):
        if not isinstance(data, bytes) or not data:
            raise ValueError("Instructions must be nonempty bytes")
        if self.failed:
            raise RuntimeError("Reconnect after a failed transmission")
        result = dict(
            instructions_sent=False,
            outcome="unknown",
            bytes_sent=0,
            did_print=False,
            ready_for_next_job=False,
            printer_state=None,
        )
        deadline = time.monotonic() + self.timeout
        try:
            while result["bytes_sent"] < len(data):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Serial transmission deadline exceeded")
                self.port.write_timeout = remaining
                start = result["bytes_sent"]
                n = self.port.write(data[start : start + 1024])
                if not n:
                    raise TimeoutError("Serial write made no progress")
                result["bytes_sent"] += n
            # flush() has no portable timeout. Poll the driver's queue instead.
            while self.port.out_waiting:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Serial output queue did not drain")
                time.sleep(0.01)
            result.update(instructions_sent=True, outcome="sent")
            return result
        except (OSError, serial.SerialException, TimeoutError) as exc:
            self.failed = True
            result["outcome"] = "unknown"
            raise PrintError(
                f"Serial transmission failed: {exc}. Do not resend blindly; a partial job may have reached the printer",
                result,
            ) from exc

    def close(self):
        self.port.close()
