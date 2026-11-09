import subprocess
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from pytsc import Printer
from pytsc.backends.cups import CUPSBackend, discover
from pytsc.backends.helpers import send
from pytsc.cli import cli
from pytsc.errors import PrintError


def completed(stdout=b"", stderr=b"", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def test_raw_submission_preserves_bytes_and_single_spool_copy(monkeypatch):
    run = Mock(return_value=completed(b"request id is TSC-42 (1 file(s))\n"))
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    data = b"BITMAP 0,0,2,1,0,\x00\xff\r\nPRINT 1,3\r\n"
    result = send(data, "cups://TSC", backend_identifier="cups")
    args, kwargs = run.call_args
    assert args[0] == [
        "lp",
        "-d",
        "TSC",
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
    ]
    assert kwargs["input"] == data
    assert kwargs["env"]["LC_ALL"] == "C"
    assert result["outcome"] == "queued"
    assert result["job_id"] == "TSC-42"
    assert not result["did_print"]


def test_discovery_merges_devices_and_queues(monkeypatch):
    run = Mock(
        side_effect=[
            completed(b"device for TSC: usb://Unknown/IEEE-1284%20Controller?location=1140000\n"),
            completed(
                b"direct usb://Unknown/IEEE-1284%20Controller?location=1140000\ndirect usb://Other/printer\nnetwork ipp\n"
            ),
        ]
    )
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    records = discover()
    assert len(records) == 2
    assert records[0]["identifier"] == "cups://TSC"
    assert records[0]["printable"] is True
    assert records[1]["printable"] is False


def test_discovery_no_queues_and_device_timeout(monkeypatch):
    run = Mock(
        side_effect=[
            completed(stderr=b"lpstat: No destinations added.", code=1),
            subprocess.TimeoutExpired("lpinfo", 20),
        ]
    )
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    assert discover()[0]["kind"] == "warning"


@pytest.mark.parametrize(
    "response", [completed(stderr=b"queue unavailable", code=1), subprocess.TimeoutExpired("lp", 1)]
)
def test_submission_failure_no_retry(monkeypatch, response):
    run = Mock(
        side_effect=response if isinstance(response, Exception) else None, return_value=response
    )
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    with pytest.raises(PrintError) as exc:
        CUPSBackend("TSC").send(b"CLS\r\n")
    assert exc.value.result["outcome"] == "unknown"
    assert run.call_count == 1


def test_reject_invalid_usb_uri():
    with pytest.raises(ValueError, match="Invalid USB"):
        CUPSBackend("usb://")


def test_printer_api(monkeypatch):
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", Mock(return_value=completed()))
    with Printer("TSC", backend="cups") as printer:
        assert printer.send(b"CLS\r\n")["outcome"] == "queued"


def test_cli_cups_does_not_pass_serial_options(tmp_path, monkeypatch):
    path = tmp_path / "job.tspl"
    path.write_bytes(b"CLS\r\n")
    monkeypatch.setattr(
        "pytsc.backends.cups.subprocess.run", Mock(return_value=completed(b"request id is TSC-1"))
    )
    result = CliRunner().invoke(cli, ["-b", "cups", "-p", "TSC", "send", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert '"outcome": "queued"' in result.output


def test_usb_reuses_queue_without_creating(monkeypatch):
    run = Mock(
        side_effect=[
            completed(b"device for Existing: usb://Unknown/Printer\n"),
            completed(b"request id is Existing-2"),
        ]
    )
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    backend = CUPSBackend("usb://Unknown/Printer")
    assert run.call_count == 0  # opening and discovering do not mutate CUPS
    result = backend.send(b"CLS\r\n")
    assert result["queue"] == "Existing"
    assert [call.args[0][0] for call in run.call_args_list] == ["lpstat", "lp"]


def test_usb_creates_and_verifies_queue(monkeypatch):
    import hashlib

    uri = "usb://Unknown/Printer?location=1140000"
    queue = "pytsc_" + hashlib.sha256(uri.encode()).hexdigest()[:16]
    run = Mock(
        side_effect=[
            completed(stderr=b"No destinations added", code=1),
            completed(),
            completed(f"device for {queue}: {uri}\n".encode()),
            completed(),
        ]
    )
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    assert CUPSBackend(uri).send(b"CLS\r\n")["queue"] == queue
    assert run.call_args_list[1].args[0] == ["lpadmin", "-p", queue, "-E", "-v", uri, "-m", "raw"]


def test_usb_permission_error_does_not_print(monkeypatch):
    run = Mock(side_effect=[completed(), completed(stderr=b"Forbidden", code=1)])
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    with pytest.raises(RuntimeError, match="sudo lpadmin"):
        CUPSBackend("usb://Unknown/Printer").send(b"CLS\r\n")
    assert run.call_count == 2


def test_usb_collision_does_not_modify_queue(monkeypatch):
    import hashlib

    uri = "usb://Unknown/Printer"
    queue = "pytsc_" + hashlib.sha256(uri.encode()).hexdigest()[:16]
    run = Mock(return_value=completed(f"device for {queue}: usb://Other/Printer\n".encode()))
    monkeypatch.setattr("pytsc.backends.cups.subprocess.run", run)
    with pytest.raises(RuntimeError, match="collision"):
        CUPSBackend(uri).send(b"CLS\r\n")
    assert run.call_count == 1
