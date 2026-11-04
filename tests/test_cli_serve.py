"""``ian serve``: each launch failure is an envelope on standard output with exit 1, and one process serves."""

import json
import os
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_serve import _allowed_origins
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from scripts.repository_root import REPOSITORY_ROOT
from tests.application._unready_database import unready_database_url

runner = CliRunner()


def _database_url(directory: Path) -> str:
    return f"sqlite:///{(directory / 'serve.sqlite3').as_posix()}"


def _failure(arguments: list[str]) -> dict[str, object]:
    result = runner.invoke(app, ["serve", *arguments])
    assert result.exit_code == 1, result.output
    assert result.stderr == ""
    document: dict[str, object] = json.loads(result.stdout)
    assert document["result"] is None
    return document


@pytest.mark.parametrize("port", ["-1", "65536", "99999"])
def test_a_port_outside_the_range_is_an_invalid_parameter(port: str, tmp_path: Path) -> None:
    document = _failure(["--port", port, "--database-url", _database_url(tmp_path)])
    assert (document["reason_code"], document["status"], document["parameters"]) == (
        "invalid_parameter",
        "error",
        ["--port"],
    )


@pytest.mark.parametrize(
    "origin",
    ["*", "null", "tauri://localhost/", "tauri://localhost/path", "localhost", "http://", "http://host:99999", ""],
)
def test_a_malformed_allowed_origin_is_an_invalid_parameter_naming_the_option(origin: str, tmp_path: Path) -> None:
    document = _failure(["--allow-origin", origin, "--database-url", _database_url(tmp_path)])
    assert (document["reason_code"], document["parameters"]) == ("invalid_parameter", ["--allow-origin"])


def test_a_good_origin_followed_by_a_bad_one_still_fails(tmp_path: Path) -> None:
    document = _failure(
        ["--allow-origin", "tauri://localhost", "--allow-origin", "*", "--database-url", _database_url(tmp_path)]
    )
    assert document["parameters"] == ["--allow-origin"]


def test_allowed_origins_are_normalized_and_deduplicated() -> None:
    assert _allowed_origins(["TAURI://Localhost", "tauri://localhost", "http://tauri.localhost", "http://h:81"]) == (
        "tauri://localhost",
        "http://tauri.localhost",
        "http://h:81",
    )
    with pytest.raises(InvalidParameterError) as caught:
        _allowed_origins(["null"])
    assert caught.value.parameters == ("--allow-origin",)


def test_a_private_memory_database_url_is_an_invalid_parameter() -> None:
    document = _failure(["--database-url", "sqlite:///:memory:"])
    assert (document["reason_code"], document["parameters"]) == ("invalid_parameter", ["--database-url"])


def test_a_database_that_is_not_ready_fails_the_launch_with_its_database_code(tmp_path: Path) -> None:
    document = _failure(["--database-url", unready_database_url(tmp_path)])
    assert str(document["reason_code"]).startswith("database_")
    assert document["parameters"] is None
    database = document["database"]
    assert isinstance(database, dict)
    assert str(database["database_path"]).endswith("not-a-database.sqlite3")


def test_a_port_that_is_in_use_is_port_unavailable(tmp_path: Path) -> None:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        document = _failure(["--port", str(port), "--database-url", _database_url(tmp_path)])
    assert (document["reason_code"], document["status"], document["parameters"]) == (
        "port_unavailable",
        "error",
        None,
    )
    assert str(port) in str(document["reason"])


@contextmanager
def _serving(directory: Path) -> Iterator[subprocess.Popen[bytes]]:
    environment = dict(
        os.environ,
        IAN_CONFIG_DIR=str(directory / "config"),
        IAN_DATA_DIR=str(directory / "data"),
        IAN_LOG_DIR=str(directory / "logs"),
    )
    with subprocess.Popen(  # noqa: S603 - fixed argument list, no untrusted input
        [sys.executable, "-m", "investment_analysis_engine.main", "serve"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            yield process
        finally:
            if process.poll() is None:
                process.kill()
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def test_one_process_prints_its_ready_line_serves_an_authenticated_request_and_exits_when_stdin_closes(
    tmp_path: Path,
) -> None:
    with _serving(tmp_path) as process:
        assert process.stdout is not None
        assert process.stdin is not None
        ready = json.loads(process.stdout.readline())
        assert list(ready) == ["port", "token"]
        assert 0 < ready["port"] < 65536
        base = f"http://127.0.0.1:{ready['port']}"

        request = urllib.request.Request(f"{base}/v1/info", headers={"Authorization": f"Bearer {ready['token']}"})
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - a loopback URL
            assert response.status == 200
            assert json.loads(response.read())["api_versions"] == ["v1"]
            assert response.headers.get("server") is None

        process.stdin.close()
        assert process.wait(timeout=30) == 0
