from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytsc.backends.pyusb import USBBackend
from pytsc.errors import PrintError


@pytest.fixture
def fake(monkeypatch):
    class Interface(list):
        bInterfaceClass = 7
        bInterfaceProtocol = 1
        bInterfaceNumber = 0
        bAlternateSetting = 0

    interface = Interface([SimpleNamespace(bEndpointAddress=1, bmAttributes=2)])
    device = Mock(bus=1, address=2)
    device.get_active_configuration.return_value = [interface]
    device.write.side_effect = lambda endpoint, data, **kw: len(data)
    core = SimpleNamespace(find=Mock(return_value=[device]), USBError=OSError)
    util = Mock()
    monkeypatch.setattr("pytsc.backends.pyusb._usb", lambda: (core, util))
    return device, util


def test_single_direction_reset_and_partial_writes(fake):
    device, util = fake
    written = bytearray()

    def write(endpoint, data, **kwargs):
        count = min(2, len(data))
        written.extend(data[:count])
        return count

    device.write.side_effect = write
    backend = USBBackend("pyusb://067b:2305", write_delay=0, soft_reset=True)
    result = backend.send(b"abc\x00\xffdef")
    assert written == b"abc\x00\xffdef"
    assert result["outcome"] == "sent" and not result["did_print"]
    device.set_interface_altsetting.assert_called_once_with(interface=0, alternate_setting=0)
    assert device.ctrl_transfer.call_args.args[:4] == (0x23, 2, 0, 0)
    assert device.ctrl_transfer.call_count == 1
    backend.close()
    util.release_interface.assert_called_once()


def test_stall_is_not_retried(fake):
    device, _ = fake
    device.write.side_effect = OSError(32, "stall")
    backend = USBBackend("pyusb://067b:2305", soft_reset=False)
    with pytest.raises(PrintError) as exc:
        backend.send(b"abc")
    assert exc.value.result["bytes_sent"] == 0
    assert device.write.call_count == 1
    with pytest.raises(RuntimeError, match="Reconnect"):
        backend.send(b"abc")
    backend.close()


def test_claim_failure_cleans_up(fake):
    device, util = fake
    util.claim_interface.side_effect = OSError("busy")
    with pytest.raises(OSError):
        USBBackend("pyusb://067b:2305")
    util.dispose_resources.assert_called_once_with(device)


def test_reset_recipient_fallback(fake):
    device, _ = fake
    device.ctrl_transfer.side_effect = [OSError(32, "pipe"), None]
    backend = USBBackend("pyusb://067b:2305", write_delay=0, soft_reset=True)
    backend.send(b"abc")
    assert device.ctrl_transfer.call_args_list[1].args[:4] == (0x21, 2, 0, 0)
    backend.close()


def test_default_skips_unsupported_reset(fake):
    device, _ = fake
    device.ctrl_transfer.side_effect = OSError(32, "pipe")
    device.clear_halt.side_effect = OSError(32, "pipe")
    backend = USBBackend("pyusb://067b:2305", write_delay=0)
    try:
        for _ in range(2):
            assert backend.send(b"abc\x00\xff")["bytes_sent"] == 5
        device.ctrl_transfer.assert_not_called()
        device.clear_halt.assert_not_called()
        assert device.write.call_count == 2
    finally:
        backend.close()
