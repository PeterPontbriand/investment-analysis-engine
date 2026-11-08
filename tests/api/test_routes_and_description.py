"""The route table is the one source: the app serves exactly its routes and the description is generated from it."""

import json
from pathlib import Path

from starlette.routing import Route

from investment_analysis_engine.api.app import create_app
from investment_analysis_engine.api.origins import normalize_origin
from investment_analysis_engine.api.routes import ROUTES
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategy_wiring import STRATEGIES
from scripts import generate_openapi
from scripts.generate_openapi import OPENAPI_FILE, openapi_description, openapi_gaps, write_openapi


def test_the_application_serves_exactly_the_routes_of_the_table(isolated_cli_settings: ProjectSettings) -> None:
    app = create_app(context=ApplicationContext(settings=isolated_cli_settings), token="t", port=1)
    served = {
        (method, route.path) for route in app.routes if isinstance(route, Route) for method in (route.methods or set())
    }
    assert served == {(route.method, route.path) for route in ROUTES}
    assert {route.method for route in ROUTES} == {"GET", "POST", "PATCH", "DELETE"}
    assert len(app.routes) == len(ROUTES)
    assert len({route.operation_id for route in ROUTES}) == len(ROUTES)


def test_every_route_declares_its_success_document_and_each_failure_status() -> None:
    for route in ROUTES:
        statuses = [status for status, _models in route.responses]
        assert statuses == sorted(statuses)
        assert {400, 401, 405, 500} <= set(statuses)
        assert sum(status < 300 for status in statuses) == 1  # exactly one success status
        assert route.success_status == {"create_watchlist": 201, "start_refresh": 202}.get(route.operation_id, 200)
        assert dict(route.responses)[400][0].__name__ == "FailureEnvelope"


def test_the_description_is_openapi_3_1_with_every_route_and_response_by_status() -> None:
    description = openapi_description()
    assert description["openapi"] == "3.1.0"
    assert set(description["paths"]) == {route.path for route in ROUTES}
    for route in ROUTES:
        operation = description["paths"][route.path][route.method.lower()]
        assert ("requestBody" in operation) == (route.request is not None)
        assert operation["operationId"] == route.operation_id
        assert set(operation["responses"]) == {str(status) for status, _models in route.responses}
        assert [item["name"] for item in operation["parameters"]] == [item.name for item in route.parameters]
    text_parameters = description["paths"]["/v1/runs/{analysis_run_id}/text"]["get"]["parameters"]
    mode = next(item for item in text_parameters if item["name"] == "mode")
    assert mode["required"] is True
    assert mode["schema"]["enum"] == ["concise", "details", "diagnostics"]
    run_schema = description["paths"]["/v1/runs/{analysis_run_id}"]["get"]["responses"]["200"]["content"]
    assert len(run_schema["application/json"]["schema"]["anyOf"]) == len(STRATEGIES)
    assert description["components"]["securitySchemes"]["bearerAuth"] == {"type": "http", "scheme": "bearer"}
    assert "WWW-Authenticate" in description["paths"]["/v1/info"]["get"]["responses"]["401"]["headers"]


def test_every_response_of_every_operation_describes_the_headers_every_response_carries() -> None:
    description = openapi_description()
    seen = 0
    for methods in description["paths"].values():
        for operation in methods.values():
            for status, response in operation["responses"].items():
                headers = response["headers"]
                assert {"Content-Language", "Vary", "Cache-Control"} <= set(headers), (operation["operationId"], status)
                assert all(headers[name]["description"].strip() for name in headers)
                seen += 1
    assert seen > 0
    info = description["paths"]["/v1/info"]["get"]["responses"]
    assert "WWW-Authenticate" in info["401"]["headers"]
    assert "Location" in description["paths"]["/v1/refreshes"]["post"]["responses"]["202"]["headers"]
    assert "Location" not in info["200"]["headers"]


def test_the_checked_in_description_is_current() -> None:
    assert openapi_gaps() == []


def test_a_missing_or_stale_description_fails_the_check(tmp_path: Path) -> None:
    missing = tmp_path / "openapi.json"
    assert len(openapi_gaps(missing)) == 1

    assert write_openapi(missing) is True
    assert openapi_gaps(missing) == []
    assert write_openapi(missing) is False

    document = json.loads(missing.read_text(encoding="utf-8"))
    document["info"]["title"] = "changed"
    missing.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    assert "out of date" in openapi_gaps(missing)[0]


def test_the_check_option_reports_drift_through_the_exit_code(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    target.write_text("{}", encoding="utf-8")

    assert generate_openapi.main(["--check"], path=target) == 1
    assert generate_openapi.main([], path=target) == 0
    assert generate_openapi.main(["--check"], path=target) == 0
    assert generate_openapi.main([], path=target) == 0
    assert OPENAPI_FILE.is_file()


def test_origins_are_scheme_host_and_optional_port_only() -> None:
    assert normalize_origin("tauri://localhost") == "tauri://localhost"
    assert normalize_origin("HTTP://Tauri.Localhost") == "http://tauri.localhost"
    assert normalize_origin("http://localhost:5173") == "http://localhost:5173"
    assert normalize_origin("http://[::1]:80") == "http://[::1]:80"
    for rejected in (
        "*",
        "null",
        "",
        "localhost",
        "http://",
        "http://host/",
        "http://host/path",
        "http://host?x=1",
        "http://user@host",
        "http://host:",
        "http://host:99999",
        "http://host:80:80",
        "http:/host",
        "1http://host",
        "http://ho st",
    ):
        assert normalize_origin(rejected) is None, rejected
