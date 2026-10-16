"""Every check a command raises itself is an ``invalid_parameter`` failure with exit 1.

The table below is section A of the SWC.4d plan, one entry per row and per command it covers. A text run writes the
sentence to standard error and nothing to standard output; a ``--json`` run writes one failure document to standard
output and nothing to standard error. Exit 2 stays what the parser returns before any command code runs.
"""

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import src.cli_database
import src.cli_workspace
from src.cli import app
from src.config import ProjectSettings
from src.reporting.documents.failure import FailureEnvelope
from src.strategies.graham_growth import cli as graham_growth_cli
from src.strategies.graham_number import cli as graham_number_cli
from src.workspace.runs import RunQuery
from tests._cli_helpers import isolated_cli_database, stub_yahoo_identity_metadata  # noqa: F401

runner = CliRunner()

_FORBIDDEN = ("input_value", "validation error for", "errors.pydantic.dev")

_GROWTH = ("--expected-growth", "5", "--aaa-yield", "4")


@dataclass(frozen=True)
class Check:
    """One row of the plan's table for one command: how to trigger it and what it must report."""

    row: str
    arguments: tuple[str, ...]
    sentence: str
    parameters: tuple[str, ...]
    json_flag: bool
    prefix: bool = False

    @property
    def label(self) -> str:
        return f"{self.row}:{' '.join(self.arguments)}"


def _direct(command: str, *extra: str, ticker: str | None = "AAPL") -> tuple[str, ...]:
    required = _GROWTH if command == "graham-growth" else ()
    return (command, *([] if ticker is None else [ticker]), *required, *extra)


def _check(
    row: str, arguments: tuple[str, ...], sentence: str, parameters: tuple[str, ...], *, json_flag: bool
) -> Check:
    return Check(row, arguments, sentence, parameters, json_flag)


_DIRECT_COMMANDS = ("momentum", "graham-number", "graham-growth", "fcf-growth")
_GRAHAM = ("graham-number", "graham-growth")
_EXCLUSIVE = "Choose only one of --details, --diagnostics, or --json."
_AS_OF_FORMAT = "--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp."


def _rows() -> list[Check]:  # noqa: PLR0912, PLR0915
    rows: list[Check] = []
    add = rows.append
    # SUP-1
    for command in _DIRECT_COMMANDS:
        add(
            _check(
                "SUP-1",
                _direct(command, "--details", "--diagnostics"),
                _EXCLUSIVE,
                ("--details", "--diagnostics"),
                json_flag=False,
            )
        )
        add(
            _check(
                "SUP-1",
                _direct(command, "--diagnostics", "--json"),
                _EXCLUSIVE,
                ("--diagnostics", "--json"),
                json_flag=False,
            )
        )
    # SUP-2 to SUP-4
    for command in ("momentum", *_GRAHAM):
        add(
            _check(
                "SUP-2",
                _direct(command, "--ticker", "MSFT"),
                "Positional TICKER and --ticker refer to different symbols.",
                ("TICKER", "--ticker"),
                json_flag=True,
            )
        )
    for command in _GRAHAM:
        add(
            _check(
                "SUP-3",
                _direct(command, ticker=None),
                f"TICKER is required. Use 'ian {command} TICKER'.",
                ("TICKER",),
                json_flag=True,
            )
        )
    for command in _DIRECT_COMMANDS:
        add(
            _check(
                "SUP-4", _direct(command, ticker=" "), "TICKER must be a non-empty symbol.", ("TICKER",), json_flag=True
            )
        )
    for command in ("momentum", *_GRAHAM):
        add(
            _check(
                "SUP-4",
                _direct(command, "--ticker", " ", ticker=None),
                "--ticker must be a non-empty symbol.",
                ("--ticker",),
                json_flag=True,
            )
        )
    # SUP-5
    for command in (*_GRAHAM, "fcf-growth"):
        add(
            _check(
                "SUP-5",
                _direct(command, "--data-provider", " "),
                "--data-provider must be non-empty when supplied.",
                ("--data-provider",),
                json_flag=True,
            )
        )
    # SUP-6 to SUP-8
    for command in _DIRECT_COMMANDS:
        add(
            _check(
                "SUP-6",
                _direct(command, "--as-of", " "),
                "--as-of must be non-empty when supplied.",
                ("--as-of",),
                json_flag=True,
            )
        )
        add(_check("SUP-7", _direct(command, "--as-of", "not-a-date"), _AS_OF_FORMAT, ("--as-of",), json_flag=True))
        add(
            _check(
                "SUP-8",
                _direct(command, "--as-of", "2024-01-01T00:00:00"),
                "Timestamp --as-of values must include an explicit timezone offset.",
                ("--as-of",),
                json_flag=True,
            )
        )
    for method in ("momentum", "graham-number", "graham-growth", "fcf-growth"):
        extra = _GROWTH if method == "graham-growth" else ()
        add(
            _check(
                "SUP-6",
                ("watchlist", "create", "W", "AAPL", "-a", method, *extra, "--as-of", " "),
                "--as-of must be non-empty when supplied.",
                ("--as-of",),
                json_flag=False,
            )
        )
        add(
            _check(
                "SUP-7",
                ("watchlist", "add-selection", "W", "AAPL", "-a", method, *extra, "--as-of", "bad"),
                _AS_OF_FORMAT,
                ("--as-of",),
                json_flag=False,
            )
        )
        add(
            _check(
                "SUP-8",
                ("watchlist", "create", "W", "AAPL", "-a", method, *extra, "--as-of", "2024-01-01T00:00:00"),
                "Timestamp --as-of values must include an explicit timezone offset.",
                ("--as-of",),
                json_flag=False,
            )
        )
    for method in ("graham-number", "graham-growth", "fcf-growth"):
        extra = _GROWTH if method == "graham-growth" else ()
        add(
            _check(
                "SUP-5",
                ("watchlist", "create", "W", "AAPL", "-a", method, *extra, "--data-provider", " "),
                "--data-provider must be non-empty when supplied.",
                ("--data-provider",),
                json_flag=False,
            )
        )
    # SUP-9: direct commands
    growth_basis = "Invalid --eps-basis: Input should be 'three_year_average' or 'fiscal_year'"
    add(
        _check(
            "SUP-9", _direct("graham-growth", "--eps-basis", "bogus"), growth_basis, ("--eps-basis",), json_flag=True
        )
    )
    add(
        _check(
            "SUP-9",
            _direct("graham-growth", "--eps-basis", "ttm"),
            growth_basis,
            ("--eps-basis",),
            json_flag=True,
        )
    )
    provider_sentence = (
        "Invalid --data-provider: Unsupported security provider 'bogus'; supported provider is 'sec_edgar'."
    )
    for command in ("graham-number", "graham-growth"):
        add(
            _check(
                "SUP-9",
                _direct(command, "--data-provider", "bogus"),
                provider_sentence,
                ("--data-provider",),
                json_flag=True,
            )
        )
    finite = "Financial override must be a finite number."
    for value in ("nan", "inf", "-inf"):
        for option in ("--eps", "--bvps", "--current-price"):
            add(
                _check(
                    "SUP-9",
                    _direct("graham-number", f"{option}={value}"),
                    f"Invalid {option}: {finite}",
                    (option,),
                    json_flag=True,
                )
            )
        for option in ("--eps", "--current-price"):
            add(
                _check(
                    "SUP-9",
                    _direct("graham-growth", f"{option}={value}"),
                    f"Invalid {option}: {finite}",
                    (option,),
                    json_flag=True,
                )
            )
        add(
            _check(
                "SUP-9",
                ("graham-growth", "AAPL", f"--expected-growth={value}", "--aaa-yield", "4"),
                f"Invalid --expected-growth: {finite}",
                ("--expected-growth",),
                json_flag=True,
            )
        )
        add(
            _check(
                "SUP-9",
                ("graham-growth", "AAPL", "--expected-growth", "5", f"--aaa-yield={value}"),
                f"Invalid --aaa-yield: {finite}",
                ("--aaa-yield",),
                json_flag=True,
            )
        )
    # SUP-9: builders
    add(
        _check(
            "SUP-9",
            ("watchlist", "create", "W", "AAPL", "-a", "graham-growth", *_GROWTH, "--eps-basis", "ttm"),
            "Invalid --eps-basis: Input should be 'three_year_average' or 'fiscal_year'",
            ("--eps-basis",),
            json_flag=False,
        )
    )
    for method in ("graham-number", "graham-growth"):
        extra = _GROWTH if method == "graham-growth" else ()
        add(
            _check(
                "SUP-9",
                ("watchlist", "create", "W", "AAPL", "-a", method, *extra, "--data-provider", "bogus"),
                "Invalid --data-provider: Unsupported security provider 'bogus'; supported provider is 'sec_edgar'.",
                ("--data-provider",),
                json_flag=False,
            )
        )
        add(
            _check(
                "SUP-9",
                ("watchlist", "add-selection", "W", "AAPL", "-a", method, *extra, "--eps", "nan"),
                "Invalid --eps: Financial override must be a finite number.",
                ("--eps",),
                json_flag=False,
            )
        )
        add(
            _check(
                "SUP-9",
                ("watchlist", "create", "W", "AAPL", "-a", method, *extra, "--current-price", "nan"),
                "Invalid --current-price: Financial override must be a finite number.",
                ("--current-price",),
                json_flag=False,
            )
        )
    add(
        _check(
            "SUP-9",
            ("watchlist", "create", "W", "AAPL", "-a", "graham-number", "--bvps", "nan"),
            "Invalid --bvps: Financial override must be a finite number.",
            ("--bvps",),
            json_flag=False,
        )
    )
    add(
        _check(
            "SUP-9",
            ("watchlist", "create", "W", "AAPL", "-a", "graham-growth", "-g", "nan", "-y", "4"),
            "Invalid --expected-growth: Financial override must be a finite number.",
            ("--expected-growth",),
            json_flag=False,
        )
    )
    add(
        _check(
            "SUP-9",
            ("watchlist", "create", "W", "AAPL", "-a", "graham-growth", "-g", "5", "-y", "nan"),
            "Invalid --aaa-yield: Financial override must be a finite number.",
            ("--aaa-yield",),
            json_flag=False,
        )
    )
    # MOM
    windows = (
        (
            "MOM-1",
            ("--short-window", "0"),
            "Invalid momentum window: --short-window must be positive (received 0).",
            ("--short-window",),
        ),
        (
            "MOM-2",
            ("--long-window", "-3"),
            "Invalid momentum window: --long-window must be positive (received -3).",
            ("--long-window",),
        ),
        (
            "MOM-3",
            ("--rsi-period", "0"),
            "Invalid momentum period: --rsi-period must be positive (received 0).",
            ("--rsi-period",),
        ),
        (
            "MOM-4",
            ("--short-window", "50", "--long-window", "20"),
            "Invalid momentum windows: --short-window (50) must be smaller than --long-window (20).",
            ("--short-window", "--long-window"),
        ),
    )
    for row, options, sentence, parameters in windows:
        add(_check(row, _direct("momentum", *options), sentence, parameters, json_flag=True))
        add(
            _check(
                row,
                ("watchlist", "create", "W", "AAPL", "-a", "momentum", *options),
                sentence,
                parameters,
                json_flag=False,
            )
        )
        add(
            _check(
                row,
                ("watchlist", "add-selection", "W", "AAPL", "-a", "momentum", *options),
                sentence,
                parameters,
                json_flag=False,
            )
        )
    add(
        _check(
            "MOM-5",
            ("momentum", "--save-run"),
            "--save-run requires an explicit ticker; the configured default ticker is not saved.",
            ("--save-run",),
            json_flag=True,
        )
    )
    # FCF
    fcf = (
        ("FCF-1", ("--growth-years", "7"), "--growth-years must be 3, 4, or 5."),
        ("FCF-2", ("--forward-policy", "nope"), "--forward-policy must be display-only, confirmation, or hard-gate."),
        ("FCF-3", ("--classification-basis", "nope"), "--classification-basis must be total-fcf or fcf-per-share."),
        ("FCF-4", ("--currency", "USDX"), "--currency must be a three-letter ISO 4217 code."),
    )
    for row, options, sentence in fcf:
        add(_check(row, _direct("fcf-growth", *options), sentence, (options[0],), json_flag=True))
        add(
            _check(
                row,
                ("watchlist", "create", "W", "AAPL", "-a", "fcf-growth", *options),
                sentence,
                (options[0],),
                json_flag=False,
            )
        )
    # GGR
    add(
        _check(
            "GGR-1",
            ("watchlist", "create", "W", "AAPL", "-a", "graham-growth", "-y", "4"),
            "--expected-growth is required when --analysis is graham-growth.",
            ("--expected-growth",),
            json_flag=False,
        )
    )
    add(
        _check(
            "GGR-2",
            ("watchlist", "add-selection", "W", "AAPL", "-a", "graham-growth", "-g", "5"),
            "--aaa-yield is required when --analysis is graham-growth.",
            ("--aaa-yield",),
            json_flag=False,
        )
    )
    # WRK
    analysis = "--analysis must be one of: momentum, graham-number, graham-growth, fcf-growth."
    add(
        _check("WRK-1", ("watchlist", "create", "W", "AAPL", "-a", "bogus"), analysis, ("--analysis",), json_flag=False)
    )
    add(
        _check(
            "WRK-1",
            ("watchlist", "add-selection", "W", "AAPL", "-a", "bogus"),
            analysis,
            ("--analysis",),
            json_flag=False,
        )
    )
    add(_check("WRK-1", ("watchlist", "remove-method", "W", "-a", "bogus"), analysis, ("--analysis",), json_flag=False))
    add(_check("WRK-1", ("runs", "list", "--analysis", "bogus"), analysis, ("--analysis",), json_flag=True))
    add(
        _check(
            "WRK-2",
            ("watchlist", "create", "W", "AAPL"),
            "--analysis is required to seed TICKER... at creation.",
            ("--analysis", "TICKER"),
            json_flag=False,
        )
    )
    add(
        _check(
            "WRK-3",
            ("watchlist", "create", "W", "--analysis", "momentum"),
            "At least one TICKER is required with --analysis.",
            ("TICKER", "--analysis"),
            json_flag=False,
        )
    )
    add(_check("WRK-4", ("watchlist", "create", "   "), "NAME must not be blank.", ("NAME",), json_flag=False))
    add(
        _check(
            "WRK-5",
            ("watchlist", "create", "W", "-a", "momentum", " "),
            "TICKER must not be empty.",
            ("TICKER",),
            json_flag=False,
        )
    )
    add(
        _check(
            "WRK-5",
            ("watchlist", "add-selection", "W", "-a", "momentum", " "),
            "TICKER must not be empty.",
            ("TICKER",),
            json_flag=False,
        )
    )
    add(
        _check(
            "WRK-5", ("watchlist", "remove-ticker", "W", " "), "TICKER must not be empty.", ("TICKER",), json_flag=False
        )
    )
    add(
        _check(
            "WRK-6", ("watchlist", "remove-entry", "W", "0"), "INDEX must be 1 or greater.", ("INDEX",), json_flag=False
        )
    )
    add(
        _check(
            "WRK-7",
            ("watchlist", "delete", "W"),
            "--yes is required when input is not interactive.",
            ("--yes",),
            json_flag=True,
        )
    )
    add(
        _check(
            "WRK-8", ("watchlist", "rename", "W", "   "), "NEW_NAME must not be blank.", ("NEW_NAME",), json_flag=True
        )
    )
    add(
        _check(
            "WRK-9",
            ("watchlist", "show", "W", "--group-by", "bogus"),
            "--group-by must be 'ticker' or 'method'.",
            ("--group-by",),
            json_flag=True,
        )
    )
    add(
        _check(
            "WRK-10", ("runs", "list", "--ticker", " "), "--ticker must not be empty.", ("--ticker",), json_flag=True
        )
    )
    add(
        _check(
            "WRK-11",
            ("runs", "list", "--status", "bogus"),
            "--status must be one of: completed, unavailable, not_applicable, failed.",
            ("--status",),
            json_flag=True,
        )
    )
    tail = (
        "is not a valid Analysis Run ID. Use the full ID exactly as shown by 'runs list' or 'refresh' "
        "— not a shortened or partial value."
    )
    add(
        _check(
            "WRK-12",
            ("runs", "list", "--refresh-id", "abc"),
            f"--refresh-id 'abc' {tail}",
            ("--refresh-id",),
            json_flag=True,
        )
    )
    add(_check("WRK-13", ("runs", "show", "abc"), f"RUN_ID 'abc' {tail}", ("RUN_ID",), json_flag=True))
    add(
        _check(
            "WRK-14",
            ("runs", "list", "--limit", "0"),
            "--limit must be between 1 and 100.",
            ("--limit",),
            json_flag=True,
        )
    )
    add(
        _check(
            "WRK-14",
            ("runs", "list", "--limit", "101"),
            "--limit must be between 1 and 100.",
            ("--limit",),
            json_flag=True,
        )
    )
    add(
        _check(
            "WRK-15",
            ("runs", "list", "--offset", "-1"),
            "--offset must be 0 or greater.",
            ("--offset",),
            json_flag=True,
        )
    )
    uuid = "00000000-0000-4000-8000-000000000000"
    add(
        _check(
            "WRK-16",
            ("runs", "show", uuid, "--details", "--diagnostics"),
            _EXCLUSIVE,
            ("--details", "--diagnostics"),
            json_flag=False,
        )
    )
    add(
        _check(
            "WRK-16",
            ("runs", "show", uuid, "--details", "--json"),
            _EXCLUSIVE,
            ("--details", "--json"),
            json_flag=False,
        )
    )
    add(
        _check(
            "WRK-17",
            ("refresh", "W", "--workers", "5"),
            "--workers must be between 1 and 4.",
            ("--workers",),
            json_flag=True,
        )
    )
    add(
        _check(
            "WRK-17",
            ("refresh", "W", "--workers", "0"),
            "--workers must be between 1 and 4.",
            ("--workers",),
            json_flag=True,
        )
    )
    # HLT, DB, EVL
    add(
        _check(
            "HLT-1",
            ("health", "--provider", "bogus"),
            "Unknown --provider 'bogus'; valid providers are: yfinance, sec_edgar.",
            ("--provider",),
            json_flag=True,
        )
    )
    for command in ("status", "upgrade"):
        add(
            Check(
                "DB-1",
                ("db", command, "--database-url", "postgresql://u:secret@host/db"),
                "Select a valid local SQLite database URL for --database-url: ",
                ("--database-url",),
                True,
                prefix=True,
            )
        )
        add(
            _check(
                "DB-2",
                ("db", command, "--database-url", "sqlite:///:memory:"),
                "Database maintenance requires a file-backed target for --database-url; "
                "private memory is not supported.",
                ("--database-url",),
                json_flag=True,
            )
        )
    add(
        Check(
            "EVL-2",
            ("evaluate", "--report", "rel.json", "--case", "NOT-A-CASE"),
            "Unknown Golden case ID 'NOT-A-CASE' for --case. Available IDs: ",
            ("--case",),
            False,
            prefix=True,
        )
    )
    add(
        _check(
            "EVL-3",
            ("evaluate", "--report", "rel.json", "--model", "m"),
            "Ollama options require --mode ollama.",
            ("--mode",),
            json_flag=False,
        )
    )
    return rows


_ROWS = _rows()


def _ids(rows: list[Check]) -> list[str]:
    return [check.label for check in rows]


@pytest.fixture(autouse=True)
def _non_interactive_input() -> Iterator[None]:
    with patch("src.cli_workspace._stdin_is_interactive", return_value=False):
        yield


def _assert_sentence(check: Check, reason: str) -> None:
    if check.prefix:
        assert reason.startswith(check.sentence), reason
    else:
        assert reason == check.sentence
    assert not any(token in reason for token in _FORBIDDEN)
    assert "secret" not in reason
    for name in check.parameters:
        assert name in reason, f"{name} is missing from the sentence"


@pytest.mark.parametrize("check", _ROWS, ids=_ids(_ROWS))
def test_the_sentence_goes_to_standard_error_and_the_command_exits_1(check: Check) -> None:
    result = runner.invoke(app, list(check.arguments))
    assert result.exit_code == 1, result.output
    if "--json" in check.arguments:
        document = json.loads(result.stdout)
        assert result.stderr == ""
        _assert_sentence(check, document["reason"])
        return
    assert result.stdout == ""
    _assert_sentence(check, result.stderr.strip())


_JSON_ROWS = [check for check in _ROWS if check.json_flag and "--json" not in check.arguments]


@pytest.mark.parametrize("check", _JSON_ROWS, ids=_ids(_JSON_ROWS))
def test_a_command_with_json_writes_one_valid_failure_document_and_nothing_to_standard_error(check: Check) -> None:
    result = runner.invoke(app, [*check.arguments, "--json"])
    assert result.exit_code == 1, result.output
    assert result.stderr == ""
    document = json.loads(result.stdout)
    envelope = FailureEnvelope.model_validate(document)
    assert document["reason_code"] == "invalid_parameter"
    assert document["status"] == "error"
    assert document["schema_version"] == 10
    assert document["result"] is None
    assert document["parameters"] == list(check.parameters)
    assert envelope.parameters == check.parameters
    _assert_sentence(check, document["reason"])


_EXCLUSIVE_JSON = [check for check in _ROWS if "--json" in check.arguments and check.row in {"SUP-1", "WRK-16"}]


@pytest.mark.parametrize("check", _EXCLUSIVE_JSON, ids=_ids(_EXCLUSIVE_JSON))
def test_the_output_flag_check_itself_writes_the_envelope_when_json_was_given(check: Check) -> None:
    result = runner.invoke(app, list(check.arguments))
    assert result.exit_code == 1
    assert result.stderr == ""
    document = json.loads(result.stdout)
    assert document["parameters"] == list(check.parameters)
    assert document["reason_code"] == "invalid_parameter"


def test_an_output_flag_failure_still_names_the_ticker_it_had_resolved() -> None:
    result = runner.invoke(app, ["momentum", "aapl", "--details", "--json"])
    document = json.loads(result.stdout)
    assert document["ticker"] == "AAPL"
    assert document["analysis"] == "momentum"
    blank = json.loads(runner.invoke(app, ["momentum", " ", "--details", "--json"]).stdout)
    assert blank["ticker"] is None
    assert blank["parameters"] == ["TICKER"]


def test_a_report_that_already_exists_is_an_invalid_parameter(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    target.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["evaluate", "--report", str(target)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert (
        result.stderr.strip() == f"--report target already exists: {target.resolve()}. Use --overwrite to replace it."
    )


def test_a_report_path_windows_would_only_partly_anchor_is_an_invalid_parameter() -> None:
    with patch("src.cli.paths.is_windows", return_value=True):
        result = runner.invoke(app, ["evaluate", "--report", "/e/x/y.json"])
    assert result.exit_code == 1
    assert result.stderr.startswith("--report path '/e/x/y.json' has a root but no drive letter")


def test_a_private_memory_target_from_the_settings_is_a_configuration_error() -> None:
    memory = ProjectSettings(database_url="sqlite:///:memory:")
    with patch.object(src.cli_database, "settings", memory):
        result = runner.invoke(app, ["db", "status", "--json"])
        text = runner.invoke(app, ["db", "upgrade"])
    document = json.loads(result.stdout)
    assert result.exit_code == 1
    assert document["reason_code"] == "configuration_error"
    assert document["parameters"] is None
    assert document["reason"] == "Database maintenance requires a file-backed target; private memory is not supported."
    assert text.exit_code == 1
    assert text.stderr.strip() == document["reason"]


# --- the parser keeps exit 2 -----------------------------------------------------------------------------------

_PARSER_REJECTIONS = [
    ("momentum", "--nope"),
    ("graham-number", "AAPL", "--nope"),
    ("graham-growth", "AAPL"),
    ("fcf-growth",),
    ("fcf-growth", "AAPL", "--growth-years", "many"),
    ("watchlist", "create"),
    ("watchlist", "add-selection", "W", "-a", "momentum"),
    ("watchlist", "remove-ticker", "W"),
    ("watchlist", "remove-entry", "W", "first"),
    ("watchlist", "rename", "W"),
    ("watchlist", "delete"),
    ("watchlist", "show"),
    ("runs", "list", "--limit", "many"),
    ("runs", "show"),
    ("refresh",),
    ("health", "--nope"),
    ("db", "status", "--nope"),
    ("evaluate",),
    ("evaluate", "--report", "r.json", "--repetitions", "0"),
    ("nope",),
]


@pytest.mark.parametrize("arguments", _PARSER_REJECTIONS, ids=[" ".join(item) for item in _PARSER_REJECTIONS])
def test_a_parser_rejection_still_exits_2_as_text(arguments: tuple[str, ...]) -> None:
    for extra in ((), ("--json",)):
        result = runner.invoke(app, [*arguments, *extra])
        assert result.exit_code == 2, result.output
        assert result.stdout == ""
        assert "Usage:" in result.stderr


# --- which check fires first ----------------------------------------------------------------------------------

_ORDER = [
    (("momentum", "AAPL", "--ticker", "MSFT", "--details", "--json"), ("TICKER", "--ticker")),
    (("momentum", " ", "--short-window", "0"), ("TICKER",)),
    (("momentum", "AAPL", "--details", "--json", "--short-window", "0"), ("--details", "--json")),
    (("momentum", "AAPL", "--short-window", "0", "--as-of", "bad"), ("--short-window",)),
    (("momentum", "--as-of", "bad", "--save-run"), ("--as-of",)),
    (("graham-number", "AAPL", "--as-of", "bad", "--data-provider", " "), ("--as-of",)),
    (("graham-number", "AAPL", "--data-provider", " ", "--eps=nan"), ("--data-provider",)),
    (("graham-number", "AAPL", "--ticker", "MSFT"), ("TICKER", "--ticker")),
    (("fcf-growth", "AAPL", "--growth-years", "9", "--as-of", "bad"), ("--growth-years",)),
    (("fcf-growth", "AAPL", "--as-of", "bad", "--currency", "XX"), ("--as-of",)),
    (("fcf-growth", "AAPL", "--data-provider", " ", "--currency", "XX"), ("--data-provider",)),
    (("fcf-growth", "AAPL", "--currency", "XX", "--classification-basis", "nope"), ("--currency",)),
    (("fcf-growth", "AAPL", "--classification-basis", "nope", "--forward-policy", "nope"), ("--classification-basis",)),
    (("watchlist", "create", "W", "AAPL", "-a", "bogus", "--short-window", "0"), ("--analysis",)),
    (("watchlist", "create", " ", "-a", "momentum", " "), ("NAME",)),
    (("watchlist", "add-selection", "Nope", " ", "-a", "bogus"), ("--analysis",)),
    (("watchlist", "add-selection", "Nope", " ", "-a", "momentum"), ("TICKER",)),
    (("watchlist", "rename", "Nope", " "), ("NEW_NAME",)),
    (("runs", "list", "--ticker", " ", "--analysis", "bogus"), ("--ticker",)),
    (("runs", "list", "--analysis", "bogus", "--status", "bogus"), ("--analysis",)),
    (("runs", "list", "--limit", "0", "--offset", "-1"), ("--limit",)),
    (("runs", "show", "abc", "--details", "--json"), ("--details", "--json")),
    (("refresh", "Nope", "--workers", "9"), ("--workers",)),
    (("evaluate", "--report", "/e/x.json", "--case", "NOPE"), ("--report",)),
    (("evaluate", "--report", "r.json", "--case", "NOPE", "--model", "m"), ("--case",)),
]


@pytest.mark.parametrize(("arguments", "expected"), _ORDER, ids=[" ".join(item[0]) for item in _ORDER])
def test_the_check_that_fires_first_today_still_fires_first(
    arguments: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    with patch("src.cli.paths.is_windows", return_value=True):
        result = runner.invoke(
            app, [*arguments, "--json"] if arguments[0] in {"momentum", "fcf-growth"} else list(arguments)
        )
    assert result.exit_code == 1, result.output
    if result.stdout.strip().startswith("{"):
        assert tuple(json.loads(result.stdout)["parameters"]) == expected
    else:
        for name in expected:
            assert name in result.stderr


# --- the workspace dispositions --------------------------------------------------------------------------------


def _watchlist_names() -> str:
    return runner.invoke(app, ["watchlist", "list"]).stdout


def test_a_blank_seed_ticker_leaves_no_watchlist_behind() -> None:
    result = runner.invoke(app, ["watchlist", "create", "Gone", "-a", "momentum", "AAPL", " "])
    assert result.exit_code == 1
    assert result.stderr.strip() == "TICKER must not be empty."
    assert "Gone" not in _watchlist_names()


def test_an_existing_name_with_a_blank_seed_ticker_reports_the_blank_ticker() -> None:
    assert runner.invoke(app, ["watchlist", "create", "Taken"]).exit_code == 0
    result = runner.invoke(app, ["watchlist", "create", "Taken", "-a", "momentum", " "])
    assert result.exit_code == 1
    assert result.stderr.strip() == "TICKER must not be empty."


def test_a_blank_ticker_leaves_the_watchlist_unchanged() -> None:
    assert runner.invoke(app, ["watchlist", "create", "Keep", "-a", "momentum", "AAPL"]).exit_code == 0
    runner.invoke(app, ["watchlist", "add-selection", "Keep", "-a", "momentum", "MSFT", " "])
    assert "Entries (1):" in runner.invoke(app, ["watchlist", "show", "Keep"]).stdout


def _corrupt_the_stored_selection(settings: ProjectSettings) -> None:
    path = settings.database_url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    connection.execute("update watchlist_entries set selection_json = ?", ('{"x":1}',))
    connection.commit()
    connection.close()


def test_add_selection_on_a_watchlist_with_an_unreadable_entry_reports_the_stored_selection(
    isolated_cli_settings: ProjectSettings,
) -> None:
    assert runner.invoke(app, ["watchlist", "create", "Old", "-a", "momentum", "AAPL"]).exit_code == 0
    _corrupt_the_stored_selection(isolated_cli_settings)
    result = runner.invoke(app, ["watchlist", "add-selection", "Old", "-a", "momentum", "MSFT"])
    assert result.exit_code == 1
    assert "its stored selection is not in a shape this version can read" in result.stderr
    assert "Usage:" not in result.stderr


def test_a_corrupt_stored_row_is_an_unexpected_failure_that_shows_none_of_the_library_text() -> None:
    assert runner.invoke(app, ["watchlist", "create", "Odd"]).exit_code == 0
    try:
        RunQuery(limit=0)
    except ValidationError as error:
        corrupt = error
    with patch("src.cli_workspace.SQLiteWatchlistRepository.add_entries", side_effect=corrupt):
        result = runner.invoke(app, ["watchlist", "add-selection", "Odd", "-a", "momentum", "AAPL"])
    assert result.exit_code == 1
    assert result.stderr.strip() == "watchlist add-selection failed unexpectedly."
    assert not any(token in result.stderr for token in _FORBIDDEN)
    assert "Usage:" not in result.stderr


def test_exit_code_1_is_not_the_parser_for_any_command_check() -> None:
    assert {check.row for check in _ROWS} >= {
        "SUP-1",
        "SUP-2",
        "SUP-3",
        "SUP-4",
        "SUP-5",
        "SUP-6",
        "SUP-7",
        "SUP-8",
        "SUP-9",
        "MOM-1",
        "MOM-2",
        "MOM-3",
        "MOM-4",
        "MOM-5",
        "FCF-1",
        "FCF-2",
        "FCF-3",
        "FCF-4",
        "GGR-1",
        "GGR-2",
        "WRK-1",
        "WRK-2",
        "WRK-3",
        "WRK-4",
        "WRK-5",
        "WRK-6",
        "WRK-7",
        "WRK-8",
        "WRK-9",
        "WRK-10",
        "WRK-11",
        "WRK-12",
        "WRK-13",
        "WRK-14",
        "WRK-15",
        "WRK-16",
        "WRK-17",
        "HLT-1",
        "DB-1",
        "DB-2",
        "EVL-2",
        "EVL-3",
    }  # EVL-1 and EVL-4 have their own tests; DB-3 has its own test


_DIRECT_MODULES = {"graham-number": graham_number_cli, "graham-growth": graham_growth_cli}
_PARITY_GROWTH = ("--expected-growth", "5", "--aaa-yield", "4")
_PARITY_CASES = [
    ("graham-number", ()),
    ("graham-number", ("--eps", "3")),
    ("graham-number", ("--bvps", "20", "--current-price", "50")),
    ("graham-number", ("--eps=nan",)),
    ("graham-number", ("--bvps=inf",)),
    ("graham-number", ("--current-price=-inf",)),
    ("graham-number", ("--data-provider", "bogus")),
    ("graham-number", ("--data-provider", " SEC_EDGAR ")),
    ("graham-number", ("--as-of", "2025-01-31")),
    ("graham-growth", _PARITY_GROWTH),
    ("graham-growth", (*_PARITY_GROWTH, "--eps", "3", "--current-price", "50")),
    ("graham-growth", (*_PARITY_GROWTH, "--eps=nan")),
    ("graham-growth", (*_PARITY_GROWTH, "--current-price=inf")),
    ("graham-growth", ("--expected-growth=nan", "--aaa-yield", "4")),
    ("graham-growth", ("--expected-growth", "5", "--aaa-yield=-inf")),
    ("graham-growth", (*_PARITY_GROWTH, "--eps-basis", "ttm")),
    ("graham-growth", (*_PARITY_GROWTH, "--eps-basis", "fiscal_year")),
    ("graham-growth", (*_PARITY_GROWTH, "--data-provider", "bogus")),
    ("graham-growth", (*_PARITY_GROWTH, "--as-of", "2025-01-31")),
]


@pytest.mark.parametrize(("command", "options"), _PARITY_CASES, ids=[" ".join((c, *o)) for c, o in _PARITY_CASES])
def test_the_direct_command_and_watchlist_create_accept_and_reject_the_same_values(
    command: str, options: tuple[str, ...]
) -> None:
    module = _DIRECT_MODULES[command]
    with (
        patch.object(module, "build_graham_resolver"),
        patch.object(module, f"_run_{command.replace('-', '_')}", return_value=("ok", 0)),
    ):
        direct = runner.invoke(app, [command, "AAPL", *options])
    watchlist = runner.invoke(app, ["watchlist", "create", "W", "AAPL", "-a", command, *options])

    assert direct.exit_code == watchlist.exit_code
    if direct.exit_code:
        assert direct.stderr.strip() == watchlist.stderr.strip()
        assert direct.stderr.strip() != ""


@pytest.mark.parametrize("basis", ["three_year_average", "ttm"])
def test_watchlist_create_ignores_an_eps_basis_for_graham_number(basis: str) -> None:
    """Graham Number has no EPS basis option; a watchlist entry ignores the flag, as it ignores --bvps for Growth."""
    watchlist = runner.invoke(app, ["watchlist", "create", "W", "AAPL", "-a", "graham-number", "--eps-basis", basis])

    assert watchlist.exit_code == 0, watchlist.output
    assert "eps_basis" not in watchlist.output
