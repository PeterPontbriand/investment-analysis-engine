"""The alias vocabulary is a bijection over every selection type's canonical method identifier."""

from typing import get_args

import pytest

from src.workspace.method_aliases import ALIAS_METHOD_IDS, ANALYSIS_ALIASES, METHOD_ID_ALIASES, alias_for_method_id
from src.workspace.requests import AnalysisSelection


def _selection_method_ids() -> set[str]:
    union = get_args(AnalysisSelection)[0]  # the Annotated wrapper's first argument is the union of models
    return {get_args(member.model_fields["method_id"].annotation)[0] for member in get_args(union)}


def test_aliases_cover_every_selection_type_method_id_exactly_once() -> None:
    assert set(ALIAS_METHOD_IDS.values()) == _selection_method_ids()
    assert len(set(ALIAS_METHOD_IDS.values())) == len(ALIAS_METHOD_IDS)
    assert set(ALIAS_METHOD_IDS) == set(ANALYSIS_ALIASES)


def test_reverse_mapping_is_derived_and_round_trips() -> None:
    for alias, method_id in ALIAS_METHOD_IDS.items():
        assert METHOD_ID_ALIASES[method_id] == alias
        assert alias_for_method_id(method_id) == alias
    assert len(METHOD_ID_ALIASES) == len(ALIAS_METHOD_IDS)


def test_an_unmapped_method_id_is_an_error_not_a_fallback() -> None:
    with pytest.raises(KeyError, match="not_a_method"):
        alias_for_method_id("not_a_method")
