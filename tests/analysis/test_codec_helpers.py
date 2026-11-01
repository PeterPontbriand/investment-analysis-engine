"""The shared codec steps of ``analysis/run_models.py``: messages, immutability of the caller's payload, refusals."""

import copy

import pytest
from pydantic import BaseModel, ConfigDict

from investment_analysis_engine.analysis.run_models import (
    StrictJsonMapping,
    decode_with_method_sections,
    decode_with_native_identifiers,
    snapshot_by_revalidation,
    validate_wire,
)


class _Result(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    value: int


class _ResultEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    result: _Result


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    value: int


class _AnalysisEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    analysis: "_Analysis"


class _Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    assembly: _Section
    result: _Section


_AnalysisEvidence.model_rebuild()

_IDENTIFIERS = {"strategy_id": "demo", "method_id": "demo_method"}
_VERSIONS = {"method_version": 1, "schema_version": 2}


def _result_payload() -> StrictJsonMapping:
    return {"result": {"value": 3, **_IDENTIFIERS, **_VERSIONS}}


def _decode_result(payload: StrictJsonMapping) -> _ResultEvidence:
    return decode_with_native_identifiers(
        _ResultEvidence, payload, label="Demo", identifiers=_IDENTIFIERS, versions=_VERSIONS
    )


def _analysis_payload() -> StrictJsonMapping:
    return {"analysis": {"assembly": {"value": 1, "method": "demo"}, "result": {"value": 2, "method": "demo"}}}


def _decode_analysis(payload: StrictJsonMapping) -> _AnalysisEvidence:
    return decode_with_method_sections(_AnalysisEvidence, payload, label="Demo", method_id="demo")


def test_snapshot_by_revalidation_returns_the_dump_after_decoding_it() -> None:
    seen: list[StrictJsonMapping] = []

    payload = snapshot_by_revalidation(_ResultEvidence(result=_Result(value=3)), seen.append)

    assert payload == {"result": {"value": 3}}
    assert seen == [payload]


def test_snapshot_by_revalidation_raises_what_the_decoder_raises() -> None:
    def refuse(_payload: StrictJsonMapping) -> object:
        raise ValueError("refused")

    with pytest.raises(ValueError, match="refused"):
        snapshot_by_revalidation(_ResultEvidence(result=_Result(value=3)), refuse)


def test_validate_wire_is_strict_and_finite() -> None:
    assert validate_wire(_Result, {"value": 4}).value == 4
    with pytest.raises(ValueError, match="valid"):
        validate_wire(_Result, {"value": "4"})
    with pytest.raises(ValueError, match="Out of range float values"):
        validate_wire(_Result, {"value": float("nan")})


def test_native_identifiers_are_checked_removed_and_the_payload_left_intact() -> None:
    payload = _result_payload()
    original = copy.deepcopy(payload)

    # The excluded keys are removed before validation, so the model sees only its own field.
    assert _decode_result(payload).result.value == 3
    assert payload == original


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda result: result.update(strategy_id="other"), "Demo native identifiers or versions do not match"),
        (lambda result: result.update(method_id=None), "Demo native identifiers or versions do not match"),
        (lambda result: result.update(method_version=2), "Demo native identifiers or versions do not match"),
        (lambda result: result.update(schema_version=True), "Demo native identifiers or versions do not match"),
        (lambda result: result.pop("schema_version"), "Demo native identifiers or versions do not match"),
    ],
)
def test_native_identifiers_or_versions_that_differ_are_refused(mutate: object, message: str) -> None:
    payload = _result_payload()
    result = payload["result"]
    assert isinstance(result, dict)
    assert callable(mutate)
    mutate(result)

    with pytest.raises(ValueError, match=message):
        _decode_result(payload)


def test_a_result_that_is_not_an_object_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="Demo result must be an object."):
        _decode_result({"result": [1]})
    with pytest.raises(ValueError, match="Demo result must be an object."):
        _decode_result({})


def test_a_payload_that_is_not_strict_json_is_refused_before_decoding() -> None:
    payload = _result_payload()
    result = payload["result"]
    assert isinstance(result, dict)
    result["value"] = float("inf")

    with pytest.raises(ValueError, match="JSON values must be finite"):
        _decode_result(payload)


def test_method_sections_are_checked_removed_and_the_payload_left_intact() -> None:
    payload = _analysis_payload()
    original = copy.deepcopy(payload)

    decoded = _decode_analysis(payload)

    assert (decoded.analysis.assembly.value, decoded.analysis.result.value) == (1, 2)
    assert payload == original


def test_a_section_with_another_method_or_none_is_refused_by_name() -> None:
    other = _analysis_payload()
    section = other["analysis"]
    assert isinstance(section, dict)
    section["result"] = {"value": 2, "method": "other"}
    with pytest.raises(ValueError, match="Demo assembly/result method mismatch."):
        _decode_analysis(other)

    missing = _analysis_payload()
    analysis = missing["analysis"]
    assert isinstance(analysis, dict)
    del analysis["assembly"]
    with pytest.raises(ValueError, match="Demo assembly/result method mismatch."):
        _decode_analysis(missing)


def test_an_analysis_that_is_not_an_object_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="Demo analysis must be an object."):
        _decode_analysis({"analysis": "x"})
