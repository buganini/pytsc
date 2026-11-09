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


def test_reject_usb_uri():
    with pytest.raises(ValueError, match="create a queue"):
        CUPSBackend("usb://Unknown/IEEE-1284%20Controller?location=1140000")


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
