"""The help endpoints, in process: each serves its document, an unknown id is a 404, and the locale is stated."""

import logging
from dataclasses import replace
from typing import Any

import pytest
from starlette.testclient import TestClient

from investment_analysis_engine.api.help_documents import (
    HelpDocumentDocument,
    HelpIndexDocument,
    HelpReferencesDocument,
    HelpTermDocument,
)
from investment_analysis_engine.api.routes import ROUTES, build_help_references_document
from investment_analysis_engine.api.term_references import EXEMPT_LOCATIONS, code_terms_by_component
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.help.bundle import HelpBundle, load_help_bundle
from investment_analysis_engine.help.locales import DEFAULT_LOCALE
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts.generate_openapi import openapi_description
from tests.api._support import AUTH, client_for
from tests.test_term_references import _enumerations, _location

ALLOWED = "tauri://localhost"


def _bundle() -> HelpBundle:
    return load_help_bundle(DEFAULT_LOCALE)


def _get(client: TestClient, path: str, **headers: str) -> Any:
    return client.get(path, headers={**AUTH, **headers})


def test_the_index_lists_every_group_and_document_of_the_bundle_in_order(
    isolated_cli_settings: ProjectSettings,
) -> None:
    bundle = _bundle()
    with client_for(isolated_cli_settings) as client:
        response = _get(client, "/v1/help")

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["schema_version", "groups", "documents"]
    assert body["schema_version"] == 1
    assert [group["id"] for group in body["groups"]] == [group.id for group in bundle.groups]
    assert [[term["id"] for term in group["terms"]] for group in body["groups"]] == [
        list(group.terms) for group in bundle.groups
    ]
    first = body["groups"][0]
    assert list(first) == ["id", "title", "terms"]
    assert list(first["terms"][0]) == ["id", "name", "definition"]
    term = bundle.terms[first["terms"][0]["id"]]
    assert first["terms"][0] == {"id": first["terms"][0]["id"], "name": term.name, "definition": term.definition}
    assert body["documents"] == [{"id": key, "title": item.title} for key, item in bundle.documents.items()]
    assert HelpIndexDocument.model_validate(body)


def test_every_glossary_term_is_reachable_and_every_served_document_with_every_section(
    isolated_cli_settings: ProjectSettings,
) -> None:
    bundle = _bundle()
    with client_for(isolated_cli_settings) as client:
        index = _get(client, "/v1/help").json()
        indexed = {term["id"] for group in index["groups"] for term in group["terms"]}
        assert indexed == set(bundle.terms)
        for term_id, term in bundle.terms.items():
            response = _get(client, f"/v1/help/terms/{term_id}")
            assert response.status_code == 200
            group = next(item for item in bundle.groups if item.id == term.group)
            assert response.json() == {
                "schema_version": 1,
                "id": term_id,
                "name": term.name,
                "definition": term.definition,
                "body": term.body,
                "group": {"id": group.id, "title": group.title},
            }
            assert HelpTermDocument.model_validate(response.json())
        assert {item["id"] for item in index["documents"]} == set(bundle.documents)
        for document_id, document in bundle.documents.items():
            response = _get(client, f"/v1/help/documents/{document_id}")
            assert response.status_code == 200
            assert response.json() == {
                "schema_version": 1,
                "id": document_id,
                "title": document.title,
                "introduction": document.introduction,
                "sections": [
                    {"id": item.id, "heading": item.heading, "level": item.level, "markdown": item.markdown}
                    for item in document.sections
                ],
            }
            assert HelpDocumentDocument.model_validate(response.json())


def test_markdown_is_served_as_written_with_its_help_links_unchanged(isolated_cli_settings: ProjectSettings) -> None:
    bundle = _bundle()
    linked = next(term_id for term_id, term in bundle.terms.items() if "](help:" in term.body)
    with client_for(isolated_cli_settings) as client:
        body = _get(client, f"/v1/help/terms/{linked}").json()["body"]
    assert body == bundle.terms[linked].body
    assert "](help:" in body


def test_a_term_without_a_body_has_an_empty_body(isolated_cli_settings: ProjectSettings) -> None:
    bare = next(term_id for term_id, term in _bundle().terms.items() if term.body == "")
    with client_for(isolated_cli_settings) as client:
        assert _get(client, f"/v1/help/terms/{bare}").json()["body"] == ""


@pytest.mark.parametrize(
    ("path", "code", "message"),
    [
        ("/v1/help/terms/no-such-term", "help_term_not_found", "No help term has this ID."),
        ("/v1/help/terms/NOT-A-term", "help_term_not_found", "No help term has this ID."),
        ("/v1/help/documents/no-such-document", "help_document_not_found", "No help document has this ID."),
        ("/v1/help/documents/" + "x" * 300, "help_document_not_found", "No help document has this ID."),
    ],
)
def test_an_id_the_bundle_lacks_answers_404_with_its_code(
    path: str, code: str, message: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = _get(client, path)
    assert response.status_code == 404
    assert (response.json()["reason_code"], response.json()["reason"]) == (code, message)


def test_a_term_id_is_not_a_document_id(isolated_cli_settings: ProjectSettings) -> None:
    bundle = _bundle()
    term_id = next(iter(bundle.terms))
    document_id = next(iter(bundle.documents))
    with client_for(isolated_cli_settings) as client:
        assert _get(client, f"/v1/help/documents/{term_id}").status_code == 404
        assert _get(client, f"/v1/help/terms/{document_id}").status_code == 404


def test_the_references_are_the_registry_and_every_strategys_tables_sorted_by_component(
    isolated_cli_settings: ProjectSettings,
) -> None:
    expected = code_terms_by_component(STRATEGIES)
    with client_for(isolated_cli_settings) as client:
        response = _get(client, "/v1/help/references")
    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["schema_version", "code_sets"]
    sets = body["code_sets"]
    assert list(sets) == sorted(sets)
    assert sets == expected
    assert all(list(sets[component]) == list(table) for component, table in expected.items())
    assert HelpReferencesDocument.model_validate(body)
    assert {term for table in sets.values() for term in table.values()} <= set(_bundle().terms)
    assert sets["FailureReasonCode"]["help_term_not_found"] == "failure-not-found"
    assert sets["FailureReasonCode"]["help_document_not_found"] == "failure-not-found"


def test_the_references_keys_are_exactly_the_enumerated_components_less_the_exemptions() -> None:
    description = openapi_description()
    components = {
        _location(path, description)
        for path, _values in _enumerations(description)
        if _location(path, description) not in EXEMPT_LOCATIONS
    }
    assert set(build_help_references_document().code_sets) == components


def test_two_tables_for_one_component_raise_and_fail_the_startup(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    clash = replace(STRATEGIES[0], code_terms={"AccountingScope": {"consolidated": "accounting-scope"}})
    with pytest.raises(ValueError, match="AccountingScope"):
        code_terms_by_component((clash,))
    monkeypatch.setattr("investment_analysis_engine.api.routes.STRATEGIES", (clash,))
    with pytest.raises(ValueError, match="AccountingScope"), client_for(isolated_cli_settings):
        pass


def test_the_help_routes_follow_the_read_routes_in_the_decided_order() -> None:
    paths = [route.path for route in ROUTES]
    start = paths.index("/v1/help")
    assert paths[start : start + 4] == [
        "/v1/help",
        "/v1/help/terms/{term_id}",
        "/v1/help/documents/{document_id}",
        "/v1/help/references",
    ]
    assert all(route.method == "GET" for route in ROUTES[: start + 4])


def test_every_response_kind_states_the_locale_and_varies_on_accept_language(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        responses = {
            "success": _get(client, "/v1/info"),
            "help success": _get(client, "/v1/help"),
            "help 404": _get(client, "/v1/help/terms/nothing"),
            "host": client.get("/v1/info", headers={**AUTH, "Host": "evil.example"}),
            "origin": client.get("/v1/info", headers={**AUTH, "Origin": "http://evil.example"}),
            "token": client.get("/v1/info"),
            "unrouted 404": _get(client, "/v1/nothing-here"),
            "unrouted 405": client.post("/v1/info", headers=AUTH),
            "preflight": client.options(
                "/v1/info", headers={"Origin": ALLOWED, "Access-Control-Request-Method": "GET"}
            ),
        }
    assert [item.status_code for item in responses.values()] == [200, 200, 404, 400, 400, 401, 404, 405, 204]
    for name, response in responses.items():
        assert response.headers["content-language"] == "en", name
        assert "Accept-Language" in response.headers["vary"], name


def test_an_allowed_origin_keeps_origin_in_vary_beside_accept_language(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        ok = _get(client, "/v1/help", Origin=ALLOWED)
        refused = client.get("/v1/help", headers={"Origin": ALLOWED})
        preflight = client.options("/v1/help", headers={"Origin": ALLOWED, "Access-Control-Request-Method": "GET"})
    for response in (ok, refused, preflight):
        assert response.headers["vary"] == "Origin, Accept-Language"
        assert response.headers["content-language"] == "en"


@pytest.mark.parametrize(
    "header",
    [None, "en-CA", "fr;q=1, en;q=0.5", "*", "en;q=0", "!!;q=zzz", "", "fr, de;q=0.1", "EN"],
)
def test_each_negotiated_header_gives_content_language_en(
    header: str | None, isolated_cli_settings: ProjectSettings
) -> None:
    headers = {} if header is None else {"Accept-Language": header}
    with client_for(isolated_cli_settings) as client:
        responses = [
            _get(client, "/v1/info", **headers),
            _get(client, "/v1/help", **headers),
            _get(client, "/v1/help/terms/nothing", **headers),
        ]
    for response in responses:
        assert response.headers["content-language"] == "en"
        assert response.headers["vary"] == "Accept-Language"
    assert [response.status_code for response in responses] == [200, 200, 404]


def test_a_preflight_may_ask_for_accept_language(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        response = client.options(
            "/v1/help",
            headers={
                "Origin": ALLOWED,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization, accept-language",
            },
        )
    assert response.status_code == 204
    assert "Accept-Language" in response.headers["access-control-allow-headers"].split(", ")


def test_the_locale_is_in_no_document(isolated_cli_settings: ProjectSettings) -> None:
    term_id = next(iter(_bundle().terms))
    with client_for(isolated_cli_settings) as client:
        for path in ("/v1/help", "/v1/help/references", f"/v1/help/terms/{term_id}"):
            assert "locale" not in _get(client, path, **{"Accept-Language": "en"}).json()


def test_an_exception_outside_an_endpoint_still_states_the_locale(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(_presented: bytes, _expected: bytes) -> bool:
        raise RuntimeError("the checks failed")

    monkeypatch.setattr("investment_analysis_engine.api.checks.secrets.compare_digest", explode)
    with caplog.at_level(logging.ERROR), client_for(isolated_cli_settings, raise_server_exceptions=False) as client:
        response = _get(client, "/v1/help")
    assert response.status_code == 500
    assert response.headers["content-language"] == "en"
    assert response.headers["vary"] == "Accept-Language"
