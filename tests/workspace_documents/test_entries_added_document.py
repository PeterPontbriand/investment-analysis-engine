"""The entries-added document and its warnings: the codes, the template rule, and the terms of the codes."""

import pytest
from pydantic import ValidationError

from investment_analysis_engine.core.entry_warnings import (
    ENTRY_WARNING_CODE_TERMS,
    EntryWarningCode,
    not_checked_warning,
    not_in_sec_list_warning,
    not_recognized_warning,
)
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.help.bundle import load_help_bundle
from investment_analysis_engine.workspace_documents.watchlist import EntryWarningDocument, build_entries_added_document


def test_every_warning_code_has_a_glossary_term_that_the_help_bundle_serves() -> None:
    bundle = load_help_bundle("en")

    assert set(ENTRY_WARNING_CODE_TERMS) == {code.value for code in EntryWarningCode}
    assert len(set(ENTRY_WARNING_CODE_TERMS.values())) == len(EntryWarningCode)
    for term in ENTRY_WARNING_CODE_TERMS.values():
        assert term in bundle.terms


@pytest.mark.parametrize(
    ("code", "text"),
    [
        (
            FailureReasonCode.PROVIDER_UNREACHABLE,
            "could not be checked, because the data providers could not be reached.",
        ),
        (
            FailureReasonCode.PROVIDER_RATE_LIMITED,
            "could not be checked, because a data provider asked the engine to wait before asking again.",
        ),
        (
            FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
            "could not be checked, because a data provider gave an unexpected answer.",
        ),
        (FailureReasonCode.PROVIDER_ERROR, "could not be checked, because a data provider gave an unexpected answer."),
        (FailureReasonCode.DATABASE_BUSY, "could not be checked, because the engine's database was not available."),
        (FailureReasonCode.DATABASE_IO_ERROR, "could not be checked, because the engine's database was not available."),
    ],
)
def test_each_not_checked_message(code: FailureReasonCode, text: str) -> None:
    warning = not_checked_warning("KO", code)

    assert warning.message == f"KO {text}"
    assert (warning.code, warning.reason_code) == (EntryWarningCode.TICKER_NOT_CHECKED, code)


def test_a_failure_that_leaves_no_ticker_unchecked_is_refused() -> None:
    with pytest.raises(ValueError, match="invalid_parameter"):
        not_checked_warning("KO", FailureReasonCode.INVALID_PARAMETER)


def test_a_warning_document_requires_the_filled_template_to_equal_the_message() -> None:
    warning = not_recognized_warning("KOO")
    ok = EntryWarningDocument(
        ticker="KOO",
        code=warning.code,
        reason_code=None,
        arguments=dict(warning.arguments),
        message=warning.message,
        template=warning.template,
    )

    assert ok.message == warning.message
    with pytest.raises(ValidationError):
        EntryWarningDocument(
            ticker="KOO",
            code=warning.code,
            reason_code=None,
            arguments=dict(warning.arguments),
            message="something else",
            template=warning.template,
        )


def test_the_builder_keeps_the_warnings_in_order() -> None:
    from datetime import UTC, datetime  # noqa: PLC0415
    from uuid import uuid4  # noqa: PLC0415

    from investment_analysis_engine.workspace.runs import Watchlist  # noqa: PLC0415

    watchlist = Watchlist(
        watchlist_id=uuid4(),
        display_name="Core",
        normalized_name="core",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=None,
        entries=(),
    )
    document = build_entries_added_document(
        watchlist, [not_recognized_warning("KOO"), not_checked_warning("MSFT", FailureReasonCode.DATABASE_BUSY)]
    )

    assert [(item.ticker, item.code.value) for item in document.warnings] == [
        ("KOO", "ticker_not_recognized"),
        ("MSFT", "ticker_not_checked"),
    ]


def test_the_sec_list_warning_document_carries_its_template_arguments_and_message() -> None:
    warning = not_in_sec_list_warning("NTR.TO", ["Graham Number", "Piotroski F-Score", "Graham Number"])

    document = EntryWarningDocument(
        ticker=warning.ticker,
        code=warning.code,
        reason_code=warning.reason_code,
        template=warning.template,
        arguments=dict(warning.arguments),
        message=warning.message,
    )

    assert document.code.value == "ticker_not_in_sec_list"
    assert document.arguments == {"ticker": "NTR.TO", "strategies": "Graham Number and Piotroski F-Score"}
    assert "{" not in document.message
