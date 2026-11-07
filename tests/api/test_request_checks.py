"""The checks every request passes before routing, in their fixed order: Host, Origin, preflight, token."""

import logging

import pytest

from investment_analysis_engine.config import ProjectSettings
from tests.api._support import AUTH, HOST, PORT, TOKEN, client_for

ALLOWED = "tauri://localhost"
OTHER_ALLOWED = "http://tauri.localhost"


def _code(response_json: dict[str, object]) -> object:
    return response_json["reason_code"]


def test_a_request_without_a_token_is_not_authenticated_even_for_an_unknown_path(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        for path in ("/v1/info", "/v1/nothing-here", "/", "/v2/info"):
            response = client.get(path)
            assert response.status_code == 401, path
            assert _code(response.json()) == "not_authenticated"
            assert response.headers["www-authenticate"] == "Bearer"
            assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "authorization",
    ["", "Bearer", "Bearer wrong-token", f"Basic {TOKEN}", TOKEN, f"Bearer {TOKEN}x", f"Bearer  {TOKEN[:-1]}"],
)
def test_a_missing_or_wrong_credential_is_not_authenticated(
    authorization: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/info", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert _code(response.json()) == "not_authenticated"


def test_the_bearer_scheme_is_case_insensitive_and_the_token_is_exact(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        assert client.get("/v1/info", headers={"Authorization": f"bearer {TOKEN}"}).status_code == 200
        assert client.get("/v1/info", headers=AUTH).status_code == 200


def test_unknown_paths_and_methods_are_not_found_only_for_an_authenticated_caller(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        missing = client.get("/v1/nothing-here", headers=AUTH)
        wrong_method = client.post("/v1/info", headers=AUTH)
        unauthenticated_method = client.post("/v1/info")
    assert (missing.status_code, _code(missing.json())) == (404, "endpoint_not_found")
    assert (wrong_method.status_code, _code(wrong_method.json())) == (405, "endpoint_not_found")
    assert "GET" in wrong_method.headers["allow"].split(", ")
    assert (unauthenticated_method.status_code, _code(unauthenticated_method.json())) == (401, "not_authenticated")


def test_a_trailing_slash_is_not_redirected(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/info/", headers=AUTH, follow_redirects=False)
    assert (response.status_code, _code(response.json())) == (404, "endpoint_not_found")


@pytest.mark.parametrize(
    "host",
    ["testserver", "127.0.0.1", f"127.0.0.1:{PORT + 1}", f"example.com:{PORT}", f"[::1]:{PORT}", f"LOCALHOST:{PORT}"],
)
def test_a_host_other_than_the_loopback_binding_is_rejected_before_anything_else(
    host: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        # No token and a disallowed origin: the Host check still answers first.
        response = client.get("/v1/info", headers={"Host": host, "Origin": "http://evil.example"})
    assert (response.status_code, _code(response.json())) == (400, "host_not_allowed")
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}"])
def test_both_loopback_spellings_of_the_host_pass(host: str, isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        assert client.get("/v1/info", headers={**AUTH, "Host": host}).status_code == 200


def test_a_request_with_no_origin_header_passes_the_origin_check(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/info", headers=AUTH)
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "vary" not in response.headers


@pytest.mark.parametrize("origin", ["http://evil.example", "null", "*", f"{ALLOWED}/", f"{ALLOWED}/path", "tauri://"])
def test_a_disallowed_origin_is_rejected_before_the_token_is_checked(
    origin: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        without_token = client.get("/v1/info", headers={"Origin": origin})
        with_token = client.get("/v1/info", headers={**AUTH, "Origin": origin})
    for response in (without_token, with_token):
        assert (response.status_code, _code(response.json())) == (400, "origin_not_allowed")
        assert "access-control-allow-origin" not in response.headers


def test_with_no_allowed_origins_every_origin_is_rejected(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/info", headers={**AUTH, "Origin": ALLOWED})
    assert (response.status_code, _code(response.json())) == (400, "origin_not_allowed")


@pytest.mark.parametrize("sent", [ALLOWED, "TAURI://LOCALHOST", OTHER_ALLOWED])
def test_an_allowed_origin_is_echoed_with_vary_and_the_exposed_challenge_header(
    sent: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED, OTHER_ALLOWED]) as client:
        ok = client.get("/v1/info", headers={**AUTH, "Origin": sent})
        unauthenticated = client.get("/v1/info", headers={"Origin": sent})
        missing = client.get("/v1/nothing-here", headers={**AUTH, "Origin": sent})
    for response in (ok, unauthenticated, missing):
        assert response.headers["access-control-allow-origin"] == sent
        assert response.headers["vary"] == "Origin"
        assert response.headers["access-control-expose-headers"] == "WWW-Authenticate"
        assert "access-control-allow-credentials" not in response.headers
    assert (ok.status_code, unauthenticated.status_code, missing.status_code) == (200, 401, 404)


def test_a_preflight_from_an_allowed_origin_is_answered_without_a_token(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": ALLOWED,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-methods"] == "GET, POST, PATCH, DELETE"
    assert response.headers["access-control-allow-headers"] == "Authorization, Content-Type"
    assert response.headers["access-control-max-age"] == "600"
    assert response.headers["vary"] == "Origin"
    assert "access-control-allow-credentials" not in response.headers


def test_a_preflight_without_an_allowed_origin_is_not_answered(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        disallowed = client.options("/v1/runs", headers={"Origin": "http://evil.example"})
        no_origin = client.options("/v1/runs")
        no_origin_with_token = client.options("/v1/runs", headers=AUTH)
    assert (disallowed.status_code, _code(disallowed.json())) == (400, "origin_not_allowed")
    assert (no_origin.status_code, _code(no_origin.json())) == (401, "not_authenticated")
    assert (no_origin_with_token.status_code, _code(no_origin_with_token.json())) == (405, "endpoint_not_found")


def test_an_options_request_without_the_request_method_header_is_not_a_preflight(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings, origins=[ALLOWED]) as client:
        without_token = client.options("/v1/runs", headers={"Origin": ALLOWED})
        with_token = client.options("/v1/runs", headers={**AUTH, "Origin": ALLOWED})
        unknown = client.options("/v1/nothing-here", headers={**AUTH, "Origin": ALLOWED})
        unknown_without_token = client.options("/v1/nothing-here", headers={"Origin": ALLOWED})
    assert (without_token.status_code, _code(without_token.json())) == (401, "not_authenticated")
    assert (with_token.status_code, _code(with_token.json())) == (405, "endpoint_not_found")
    assert with_token.headers["allow"] == "GET"
    assert "access-control-allow-methods" not in with_token.headers
    assert (unknown.status_code, _code(unknown.json())) == (404, "endpoint_not_found")
    assert (unknown_without_token.status_code, _code(unknown_without_token.json())) == (401, "not_authenticated")


def test_head_and_other_undeclared_methods_are_not_allowed_with_the_declared_method_named(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        responses = [
            client.head("/v1/info", headers=AUTH),
            client.post("/v1/info", headers=AUTH),
            client.put("/v1/runs", headers=AUTH),
            client.delete("/v1/watchlists", headers=AUTH),
        ]
    for response in responses:
        assert response.status_code == 405
        assert response.headers["allow"] == "GET"
    assert [response.status_code for response in responses[1:]] == [405, 405, 405]
    assert all(_code(response.json()) == "endpoint_not_found" for response in responses[1:])


def test_an_exception_outside_an_endpoint_is_the_fixed_execution_error_and_is_logged_without_the_token(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(_presented: bytes, _expected: bytes) -> bool:
        raise RuntimeError("the checks failed")

    monkeypatch.setattr("investment_analysis_engine.api.checks.secrets.compare_digest", explode)
    with caplog.at_level(logging.ERROR), client_for(isolated_cli_settings, raise_server_exceptions=False) as client:
        response = client.get("/v1/info", headers=AUTH)
    assert response.status_code == 500
    body = response.json()
    assert (body["reason_code"], body["reason"]) == ("execution_error", "The request failed unexpectedly.")
    assert TOKEN not in response.text
    assert "the checks failed" not in response.text
    raised = [record.exc_info[1] for record in caplog.records if record.exc_info is not None]
    assert any("the checks failed" in str(exception) for exception in raised)
    assert TOKEN not in "\n".join(f"{record.getMessage()}{record.exc_text or ''}" for record in caplog.records)


def test_every_response_is_uncached_json(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        for response in (
            client.get("/v1/info", headers=AUTH),
            client.get("/v1/info"),
            client.get("/nope", headers=AUTH),
        ):
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["content-type"] == "application/json"


def test_the_host_constant_matches_the_client_base_url() -> None:
    assert f"127.0.0.1:{PORT}" == HOST
