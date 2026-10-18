import io
import json

import pytest

from lambda_auth.local import main


def test_local_cli_invokes_handler_from_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    event = {
        "rawPath": "/health",
        "requestContext": {"http": {"method": "GET"}},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))

    assert main() == 0

    output = capsys.readouterr()
    assert json.loads(output.out)["statusCode"] == 200
    assert output.err == ""


def test_local_cli_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not-json"))

    assert main() == 2

    output = capsys.readouterr()
    assert output.out == ""
    assert "JSON válido" in output.err


def test_local_cli_rejects_non_object_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("[]"))

    assert main() == 2

    output = capsys.readouterr()
    assert output.out == ""
    assert "JSON válido" in output.err
