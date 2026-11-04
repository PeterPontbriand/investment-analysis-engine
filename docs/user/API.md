# Local HTTP API

`ian serve` runs a local HTTP interface that returns the documents the command line writes with `--json`, so another
program on the same computer can read watchlists, saved runs and run comparisons without parsing terminal output. This
page is for the authors of such a program, called a client here. It is not reachable from another computer.

For the rules that say what may change inside `/v1`, see
[What may change in the JSON output](USAGE.md#what-may-change-in-the-json-output). The machine-readable description of
every endpoint and response is [`schemas/openapi.json`](../../schemas/openapi.json); the server does not serve it.

## Starting the server

```bash
uv run ian serve
```

| Option | Meaning |
| :--- | :--- |
| `--port` | The port on `127.0.0.1` to listen on, 0 to 65535. The default, 0, lets the operating system choose. |
| `--allow-origin` | An origin whose pages may call the API, given as `scheme://host` or `scheme://host:port`. Repeatable. None by default. |
| `--database-url` | A SQLite target to use instead of the configured one, validated exactly as `ian db status` validates it. |

Once the server is listening, `ian serve` writes one line of JSON to standard output and nothing else:

```json
{"port": 52714, "token": "Zq3m...u7A"}
```

The line appears only after the server has started, so a client may read it as the signal to connect. The token is new
on every launch, is never written to a file or a log, and must be sent with every request. Everything else the server
reports goes to the log file.

The server runs as one process and exits with code 0 when its standard input reaches end of file or on Ctrl+C. A request
in flight gets up to five seconds to finish. A client that starts the server should hold its standard input open and
close it to stop the server.

A launch that fails writes one [failure document](#errors) to standard output and exits with code 1:

| Cause | `reason_code` | `parameters` |
| :--- | :--- | :--- |
| `--port` outside 0 to 65535 | `invalid_parameter` | `["--port"]` |
| `--allow-origin` that is not `scheme://host[:port]` | `invalid_parameter` | `["--allow-origin"]` |
| `--database-url` rejected, or naming private memory | `invalid_parameter` | `["--database-url"]` |
| The database is not ready | its `database_*` code | `null` |
| The port is in use, or not permitted | `port_unavailable` | `null` |

## Authentication

Every request carries the token in the `Authorization` header:

```text
Authorization: Bearer <token>
```

The token is never accepted in a path, a query string or a body. A request without a valid token gets status 401 and
`WWW-Authenticate: Bearer`, whatever its path: an unknown path is 401 too, and only a caller that presents the token
learns that a path does not exist.

## Host and Origin

The checks run in this order, before the request is routed:

1. **Host.** The `Host` header must be exactly `127.0.0.1:<port>` or `localhost:<port>`. Anything else is `host_not_allowed`.
2. **Origin.** A request with no `Origin` header passes. A request with one must name an origin given to
   `--allow-origin`; otherwise it is `origin_not_allowed`. Comparison is exact after lower-casing the scheme and the host.
   `*` and `null` are never accepted, so a page must be loaded from an origin other than `null`, for example a custom
   scheme or `localhost`.
3. **Preflight.** An `OPTIONS` request from an allowed origin that carries `Access-Control-Request-Method` is a
   preflight and is answered without the token: status 204, method `GET` only, header `Authorization` only,
   `Access-Control-Max-Age: 600`. Any other `OPTIONS` request goes through the token check and then routing like any
   other request: 405 on a known path, 404 on an unknown one.
4. **Token.** As above.

For an allowed origin every response carries `Access-Control-Allow-Origin` with that origin, `Vary: Origin` and
`Access-Control-Expose-Headers: WWW-Authenticate`. The API never sets `Access-Control-Allow-Credentials`.

## Responses

Every body is JSON in UTF-8, written compact and in field order, with `Content-Type: application/json` and
`Cache-Control: no-store`. A document has the shape the command line gives it; its whitespace and key order are not
guaranteed. Compare parsed values, not text.

Response headers are not part of the contract, except `Content-Type` and `WWW-Authenticate`: other headers may be added,
changed or removed within `/v1`.

## Errors

Every response that is not 2xx has a [failure document](../../schemas/failure.schema.json) as its body. A client branches
on `reason_code`; the HTTP status is coarse and `reason` is a message for people. `parameters` names the offending query
or path parameter. The five codes only the API and `ian serve` use are `not_authenticated`, `host_not_allowed`,
`origin_not_allowed`, `endpoint_not_found` and `port_unavailable`.

| HTTP status | `reason_code` |
| :--- | :--- |
| 400 | `invalid_parameter`, `host_not_allowed`, `origin_not_allowed` |
| 401 | `not_authenticated` |
| 404 | `analysis_run_not_found`, `watchlist_not_found`, `endpoint_not_found` |
| 405 | `endpoint_not_found` (a method the endpoint does not declare, `HEAD` included), with an `Allow` header naming the declared method |
| 503 | `database_busy` |
| 500 | every other code, including every other `database_*` code and `execution_error` |

An unexpected failure, whether in an endpoint or in the checks before it, is `execution_error` with a fixed message and
status 500; its detail goes to the log. `port_unavailable` occurs only
at launch.

A parameter is rejected with `invalid_parameter`, naming it, when it is unknown, when it is given more than once, when it
is malformed (including an ID that is not a UUID in a path, which is never a 404), or when its value is out of range.

## Endpoints

All endpoints use `GET` and sit under `/v1`. Any other method, `HEAD` included, is answered 405 `endpoint_not_found`.

| Path | Query parameters | Response |
| :--- | :--- | :--- |
| `/v1/info` | none | `schema_version`, `api_versions`, `engine_version` and `sec_identity_configured`; never the identity itself |
| `/v1/strategies` | none | `schema_version` and `items`, each with `analysis`, `method` and `label` |
| `/v1/watchlists` | none | the watchlist list document |
| `/v1/watchlists/{watchlist_id}` | none | the watchlist document |
| `/v1/runs` | `ticker`, `method_id`, `status`, `refresh_id`, `limit`, `offset` | the runs list document |
| `/v1/runs/{analysis_run_id}` | none | the saved run's own strategy document |
| `/v1/runs/{analysis_run_id}/text` | `mode` (required): `concise`, `details` or `diagnostics` | `schema_version`, `mode` and `text` |
| `/v1/refreshes/{refresh_id}/compare` | none | the runs compare document |

On `/v1/runs`, `limit` is 1 to 100 and defaults to 20, and `offset` defaults to 0. `method_id` is a method identifier
as `/v1/strategies` lists it. The document says whether more rows follow with `has_more`; there is no total.

The documents are described by the files in [`schemas/`](../../schemas/) and by
[`schemas/openapi.json`](../../schemas/openapi.json), which also describes the three documents only the API serves.
