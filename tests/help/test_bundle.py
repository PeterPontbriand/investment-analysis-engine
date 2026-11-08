"""The help bundle model refuses a bundle that does not hold together, and the loader returns a validated bundle."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from investment_analysis_engine.help.bundle import HelpBundle, HelpTerm, load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE


def bundle_data() -> dict[str, Any]:
    """Return the data of a small, coherent bundle."""
    return {
        "terms": {
            "alpha": {
                "name": "Alpha",
                "definition": "Alpha defined.",
                "body": "See [Beta](help:terms/beta) and [the guide](help:documents/guide#first).",
                "group": "one",
            },
            "beta": {"name": "Beta", "definition": "Beta defined.", "body": "", "group": "one"},
        },
        "groups": [{"id": "one", "title": "One", "terms": ["alpha", "beta"]}],
        "documents": {
            "guide": {
                "title": "Guide",
                "introduction": "Start with [Alpha](help:terms/alpha) or [the guide](help:documents/guide).",
                "sections": [
                    {"id": "first", "heading": "First", "level": 2, "markdown": "See [Beta](help:terms/beta)."},
                    {
                        "id": "second",
                        "heading": "Second",
                        "level": 2,
                        "markdown": "Back to [first](help:documents/guide#first) and [web](https://example.com).",
                    },
                ],
            }
        },
    }


def test_a_coherent_bundle_validates() -> None:
    bundle = HelpBundle.model_validate(bundle_data())
    assert bundle.terms["alpha"].group == "one"
    assert bundle.groups[0].terms == ("alpha", "beta")


def test_a_term_in_no_group_fails_naming_the_term() -> None:
    data = bundle_data()
    data["groups"][0]["terms"] = ["alpha"]
    with pytest.raises(ValidationError, match="term 'beta' is in 0 groups"):
        HelpBundle.model_validate(data)


def test_a_term_in_two_groups_fails_naming_the_term() -> None:
    data = bundle_data()
    data["groups"].append({"id": "two", "title": "Two", "terms": ["beta"]})
    with pytest.raises(ValidationError, match="term 'beta' is in 2 groups"):
        HelpBundle.model_validate(data)


def test_a_term_whose_group_is_not_the_group_that_lists_it_fails() -> None:
    data = bundle_data()
    data["terms"]["beta"]["group"] = "elsewhere"
    with pytest.raises(ValidationError, match="term 'beta' names group 'elsewhere' but group 'one' lists it"):
        HelpBundle.model_validate(data)


def test_a_group_listing_a_missing_term_fails_naming_the_group_and_the_id() -> None:
    data = bundle_data()
    data["groups"][0]["terms"].append("gamma")
    with pytest.raises(ValidationError, match="group 'one' lists term 'gamma', which does not exist"):
        HelpBundle.model_validate(data)


@pytest.mark.parametrize(
    ("place", "reason"),
    [
        ("term body", "term 'alpha' has the link 'help:terms/nothing', which names no term 'nothing'"),
        (
            "introduction",
            "document 'guide' introduction has the link 'help:documents/nothing', which names no document 'nothing'",
        ),
        (
            "section",
            "document 'guide' section 'first' has the link 'help:documents/guide#nothing', "
            "which names no section 'nothing' of document 'guide'",
        ),
    ],
)
def test_a_link_that_resolves_to_nothing_fails_naming_where_and_the_link(place: str, reason: str) -> None:
    data = bundle_data()
    if place == "term body":
        data["terms"]["alpha"]["body"] = "See [x](help:terms/nothing)."
    elif place == "introduction":
        data["documents"]["guide"]["introduction"] = "See [x](help:documents/nothing)."
    else:
        data["documents"]["guide"]["sections"][0]["markdown"] = "See [x](help:documents/guide#nothing)."
    with pytest.raises(ValidationError, match=reason.replace("(", r"\(").replace(")", r"\)")):
        HelpBundle.model_validate(data)


@pytest.mark.parametrize("level", [1, 7, 0, -1])
def test_a_section_level_outside_two_to_six_fails(level: int) -> None:
    data = bundle_data()
    data["documents"]["guide"]["sections"][0]["level"] = level
    with pytest.raises(ValidationError, match="level"):
        HelpBundle.model_validate(data)


@pytest.mark.parametrize("level", [2, 3, 6])
def test_a_section_level_from_two_to_six_passes(level: int) -> None:
    data = bundle_data()
    data["documents"]["guide"]["sections"][0]["level"] = level
    assert HelpBundle.model_validate(data).documents["guide"].sections[0].level == level


def test_a_help_link_of_another_kind_fails() -> None:
    data = bundle_data()
    data["terms"]["beta"]["body"] = "See [x](help:other/beta)."
    with pytest.raises(ValidationError, match="is neither a term link nor a document link"):
        HelpBundle.model_validate(data)


def test_a_section_link_needs_a_section_id() -> None:
    data = bundle_data()
    data["terms"]["beta"]["body"] = "See [x](help:documents/guide#)."
    with pytest.raises(ValidationError, match="names no section ''"):
        HelpBundle.model_validate(data)


def test_every_model_is_frozen_and_refuses_an_extra_field() -> None:
    bundle = HelpBundle.model_validate(bundle_data())
    with pytest.raises(ValidationError):
        bundle.terms["alpha"].name = "Other"
    extra = bundle_data()
    extra["terms"]["alpha"]["note"] = "x"
    with pytest.raises(ValidationError, match="note"):
        HelpBundle.model_validate(extra)
    top = bundle_data()
    top["extra"] = 1
    with pytest.raises(ValidationError, match="extra"):
        HelpBundle.model_validate(top)
    assert HelpTerm.model_config["frozen"] is True
    assert HelpTerm.model_config["extra"] == "forbid"


def test_the_loader_returns_a_validated_bundle_and_a_second_call_the_same_object() -> None:
    first = load_help_bundle(DEFAULT_LOCALE)
    assert isinstance(first, HelpBundle)
    assert first.terms
    assert first.documents
    assert HelpBundle.model_validate(first.model_dump(mode="json")) == first
    assert load_help_bundle(DEFAULT_LOCALE) is first
