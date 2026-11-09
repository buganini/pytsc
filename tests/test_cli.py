import json

from click.testing import CliRunner
from PIL import Image

from pytsc.cli import cli


def test_offline_round_trip(tmp_path):
    source = tmp_path / "label.png"
    output = tmp_path / "label.tspl"
    preview = tmp_path / "preview.png"
    Image.new("1", (600, 360), 1).save(source)
    runner = CliRunner()
    result = runner.invoke(cli, ["convert", "-l", "50x30", str(source), "-o", str(output)])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        cli,
        ["analyze", str(output), "--json", "--output-dir", str(tmp_path / "extract")],
    )
    assert result.exit_code == 0, result.output
    assert any(r.get("byte_count") == 27000 for r in json.loads(result.output))
    result = runner.invoke(cli, ["preview", "-l", "50x30", str(source), "-o", str(preview)])
    assert result.exit_code == 0, result.output
    assert Image.open(preview).size == (600, 360)


def test_missing_printer_and_invalid_image(tmp_path):
    source = tmp_path / "bad.png"
    source.write_bytes(b"broken")
    result = CliRunner().invoke(cli, ["print", "-l", "50x30", "--json", str(source)])
    assert result.exit_code == 1
    assert "--printer" in json.loads(result.output)["error"]
    result = CliRunner().invoke(
        cli, ["convert", "-l", "50x30", str(source), "-o", str(tmp_path / "out")]
    )
    assert result.exit_code == 1


def test_env_and_models():
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "env", "--json"], env={"PYTSC_BAUDRATE": "19200"})
    assert json.loads(result.output)["baudrate"] == 19200
    result = runner.invoke(cli, ["info", "models", "--json"])
    assert all(not m["hardware_verified"] for m in json.loads(result.output))


def test_discover_all_and_explicit_backend(monkeypatch):
    from pytsc.backends import helpers

    monkeypatch.setattr(helpers, "discover_usb", lambda: [])
    monkeypatch.setattr(helpers, "discover_serial", lambda: [{"identifier": "COM3"}])
    monkeypatch.setattr(helpers, "discover_cups", lambda: [{"identifier": "cups://TSC"}])
    runner = CliRunner()
    result = runner.invoke(cli, ["discover", "--json"], env={"PYTSC_BACKEND": ""})
    assert result.exit_code == 0, result.output
    assert {r["backend"] for r in json.loads(result.output)} == {"serial", "cups"}
    for args, env in [
        (["-b", "cups", "discover", "--json"], {}),
        (["discover", "--json"], {"PYTSC_BACKEND": "cups"}),
    ]:
        result = runner.invoke(cli, args, env=env)
        assert [r["backend"] for r in json.loads(result.output)] == ["cups"]


def test_discover_all_retains_partial_results(monkeypatch):
    from pytsc.backends import helpers

    monkeypatch.setattr(helpers, "discover_usb", lambda: [])
    monkeypatch.setattr(helpers, "discover_serial", lambda: [{"identifier": "COM3"}])

    def fail():
        raise RuntimeError("CUPS not installed")

    monkeypatch.setattr(helpers, "discover_cups", fail)
    result = helpers.discover()
    assert result[0]["identifier"] == "COM3"
    assert result[1] == {"kind": "warning", "backend": "cups", "message": "CUPS not installed"}


def test_usb_print_auto_backend_and_overrides(monkeypatch, tmp_path):
    from unittest.mock import Mock

    image = tmp_path / "label.png"
    Image.new("1", (600, 360), 1).save(image)
    submit = Mock(return_value={"outcome": "queued", "bytes_sent": 27000})
    monkeypatch.setattr("pytsc.cli.send", submit)
    uri = "usb://Prolific%20Technology%20Inc./IEEE-1284%20Controller?location=1140000"
    runner = CliRunner()
    command = ["-p", uri, "print", "-l", "50x30", "--gap", "2", str(image)]
    result = runner.invoke(cli, command, env={"PYTSC_BACKEND": ""})
    assert result.exit_code == 0, result.output
    assert submit.call_args.args[2] == "cups"
    assert "baudrate" not in submit.call_args.kwargs
    result = runner.invoke(cli, ["-b", "serial", *command])
    assert result.exit_code == 0, result.output
    assert submit.call_args.args[2] == "serial"
    result = runner.invoke(cli, command, env={"PYTSC_BACKEND": "serial"})
    assert result.exit_code == 0, result.output
    assert submit.call_args.args[2] == "serial"
