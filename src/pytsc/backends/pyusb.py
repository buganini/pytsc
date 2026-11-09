"""Experimental PL2305 unidirectional USB transport. Never retries payload data."""

import math
import re
import time

from ..errors import PrintError


def _usb():
    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise RuntimeError("Install pytsc[usb] and a system libusb library") from exc
    return usb.core, usb.util


def discover():
    core, util = _usb()
    result = []
    for device in core.find(find_all=True, idVendor=0x067B, idProduct=0x2305):
        result.append(
            {
                "identifier": f"pyusb://067b:2305/{device.bus}/{device.address}",
                "vendor_id": device.idVendor,
                "product_id": device.idProduct,
                "bus": device.bus,
                "address": device.address,
            }
        )
        util.dispose_resources(device)
    return result


class USBBackend:
    def __init__(
        self, identifier, *, timeout=120, chunk_size=512, write_delay=0.01, soft_reset=True
    ):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if type(chunk_size) is not int or not 1 <= chunk_size <= 65536:
            raise ValueError("chunk_size must be 1..65536")
        if not math.isfinite(write_delay) or write_delay < 0:
            raise ValueError("write_delay must be finite and nonnegative")
        match = re.fullmatch(
            r"pyusb://(?:0x)?067b:(?:0x)?2305(?:/(\d+)/(\d+))?", identifier or "", re.I
        )
        if not match:
            raise ValueError("Experimental pyusb supports only pyusb://067b:2305[/BUS/ADDRESS]")
        self.core, self.util = _usb()
        devices = list(self.core.find(find_all=True, idVendor=0x067B, idProduct=0x2305))
        if match[1]:
            devices = [d for d in devices if (d.bus, d.address) == (int(match[1]), int(match[2]))]
        if len(devices) != 1:
            raise ValueError("Expected one PL2305; use discover and select its bus/address")
        self.device = devices[0]
        self.timeout, self.chunk_size, self.write_delay = timeout, chunk_size, write_delay
        self.soft_reset = soft_reset
        self.claimed = False
        self.failed = False
        try:
            config = self.device.get_active_configuration()
            candidates = [i for i in config if i.bInterfaceClass == 7 and i.bInterfaceProtocol == 1]
            if len(candidates) != 1:
                raise ValueError("PL2305 must expose one unidirectional printer interface")
            interface = candidates[0]
            self.interface = interface.bInterfaceNumber
            endpoints = [
                e.bEndpointAddress
                for e in interface
                if (e.bmAttributes & 3) == 2 and not (e.bEndpointAddress & 0x80)
            ]
            if len(endpoints) != 1:
                raise ValueError("Expected one bulk OUT endpoint")
            self.endpoint = endpoints[0]
            # Do not detach system drivers or reset the whole device automatically.
            self.util.claim_interface(self.device, self.interface)
            self.claimed = True
            self.device.set_interface_altsetting(
                interface=self.interface, alternate_setting=interface.bAlternateSetting
            )
        except Exception:
            self.close()
            raise

    def _reset(self, milliseconds):
        # USB Printer Class SOFT_RESET; CUPS tries OTHER before INTERFACE.
        try:
            self.device.ctrl_transfer(0x23, 2, 0, self.interface, None, timeout=milliseconds)
        except self.core.USBError as exc:
            if getattr(exc, "errno", None) != 32:  # PIPE/unsupported recipient only
                raise
            self.device.ctrl_transfer(0x21, 2, 0, self.interface, None, timeout=milliseconds)
        self.device.clear_halt(self.endpoint)

    def send(self, data):
        if not isinstance(data, bytes) or not data:
            raise ValueError("Instructions must be nonempty bytes")
        if self.failed:
            raise RuntimeError("Reconnect after a failed USB transmission")
        result = dict(
            instructions_sent=False,
            outcome="unknown",
            bytes_sent=0,
            did_print=False,
            ready_for_next_job=False,
            printer_state=None,
        )
        deadline = time.monotonic() + self.timeout

        def remaining():
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise TimeoutError("USB transmission deadline exceeded")
            return max(1, math.ceil(seconds * 1000))

        stage = "pre-send reset"
        try:
            if self.soft_reset:
                self._reset(remaining())
            stage = "bulk write"
            while result["bytes_sent"] < len(data):
                start = result["bytes_sent"]
                count = self.device.write(
                    self.endpoint, data[start : start + self.chunk_size], timeout=remaining()
                )
                if not count:
                    raise TimeoutError("USB write made no progress")
                result["bytes_sent"] += count
                if result["bytes_sent"] < len(data) and self.write_delay:
                    time.sleep(min(self.write_delay, remaining() / 1000))
            # No immediate post-job reset: it can discard unread adapter buffers.
            result.update(instructions_sent=True, outcome="sent")
            return result
        except (OSError, TimeoutError) as exc:
            self.failed = True
            raise PrintError(
                f"Direct USB {stage} failed: {exc}; no automatic retry",
                result,
            ) from exc

    def close(self):
        try:
            if self.claimed:
                self.util.release_interface(self.device, self.interface)
        finally:
            self.claimed = False
            self.util.dispose_resources(self.device)
