import pytest

from pytsc.backends.helpers import send
from pytsc.backends.serial import SerialBackend
from pytsc.errors import PrintError


class Port:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.data = bytearray()
        self.out_waiting = 0
        self.closed = False

    def write(self, data):
        n = min(3, len(data))
        self.data.extend(data[:n])
        return n

    def close(self):
        self.closed = True


@pytest.fixture
def port(monkeypatch):
    created = []

    def factory(**kwargs):
        p = Port(**kwargs)
        created.append(p)
        return p

    monkeypatch.setattr("pytsc.backends.serial.serial.Serial", factory)
    return created


def test_partial_writes_and_close(port):
    result = send(
        b"abc\x00\x11\x13def",
        "serial:///dev/test",
        baudrate=19200,
        flow_control="rtscts",
    )
    p = port[0]
    assert p.data == b"abc\x00\x11\x13def"
    assert p.closed
    assert p.options["port"] == "/dev/test"
    assert p.options["baudrate"] == 19200
    assert p.options["rtscts"] is True
    assert p.options["xonxoff"] is False
    assert result["outcome"] == "sent"
    assert result["did_print"] is False
    assert result["ready_for_next_job"] is False


def test_no_progress_invalidates_session(port):
    backend = SerialBackend("test")
    port[0].write = lambda data: 0
    with pytest.raises(PrintError) as error:
        backend.send(b"abc")
    assert error.value.result["outcome"] == "unknown"
    with pytest.raises(RuntimeError, match="Reconnect"):
        backend.send(b"abc")
    backend.close()


def test_failure_closes_connection(port, monkeypatch):
    def fail(self, data):
        raise OSError("disconnected")

    monkeypatch.setattr(Port, "write", fail)
    with pytest.raises(PrintError):
        send(b"abc", "test")
    assert port[0].closed


def test_drain_timeout(port):
    backend = SerialBackend("test", timeout=0.01)
    port[0].out_waiting = 1
    with pytest.raises(PrintError, match="drain"):
        backend.send(b"abc")
    backend.close()


def test_reject_software_flow_control(port):
    with pytest.raises(ValueError, match="XON/XOFF"):
        SerialBackend("test", flow_control="xonxoff")
    assert not port
