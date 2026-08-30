"""Regression tests for exhaustive investor-facing calculation statuses."""

from src.core.analysis_status import CalculationStatus
from src.reporting.presentation import STATUS_LABELS, humanized_status


def test_every_calculation_status_has_plain_english_label() -> None:
    """No machine enum spelling leaks into investor-facing status prose."""
    assert set(STATUS_LABELS) == set(CalculationStatus)
    assert [humanized_status(status) for status in CalculationStatus] == [
        "ok",
        "not applicable",
        "invalid input",
        "input unavailable",
        "provider error",
    ]
