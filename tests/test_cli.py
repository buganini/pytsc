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
