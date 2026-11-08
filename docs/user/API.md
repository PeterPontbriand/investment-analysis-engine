# Local HTTP API

`ian serve` runs a local HTTP interface that returns the documents the command line writes with `--json`, so another
program on the same computer can read and change watchlists, analyze a ticker, refresh a watchlist, and read saved runs and run comparisons without parsing terminal output. This
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

A [refresh job](#refresh-jobs) that is running is stopped the moment the server begins to stop, so its five seconds run
beside those of the requests and not after them. A job still running when they end is abandoned: the server writes one
line to the log saying that the refresh did not finish and that its unfinished jobs were not saved, and the process ends
at once, still with exit code 0. Jobs the refresh had already saved stay saved; a job that was running is not saved. The
job is cut short this way because a provider request has no time limit of its own, so waiting for it could keep the
process alive indefinitely.

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
   preflight and is answered without the token: status 204, exactly the methods the endpoints declare (`GET`, `POST`,
   `PATCH` and `DELETE`), the headers `Authorization` and `Content-Type` only, `Access-Control-Max-Age: 600`. Any other `OPTIONS` request goes through the token check and then routing like any
   other request: 405 on a known path, 404 on an unknown one.
4. **Token.** As above.

For an allowed origin every response carries `Access-Control-Allow-Origin` with that origin, `Vary: Origin` and
`Access-Control-Expose-Headers: WWW-Authenticate`. The API never sets `Access-Control-Allow-Credentials`.

## Responses

Every body is JSON in UTF-8, written compact and in field order, with `Content-Type: application/json` and
`Cache-Control: no-store`. A document has the shape the command line gives it; its whitespace and key order are not
guaranteed. Compare parsed values, not text.

Every response, a refusal and the answer to a preflight included, also carries `Content-Language`, the tag of the locale
the engine's text is in, and `Vary` naming `Accept-Language` (see [Locales](#locales)). Response headers are not part of
the contract, except `Content-Type`, `WWW-Authenticate`, `Content-Language` and `Vary`: other headers may be added,
changed or removed within `/v1`.

## Errors

Every response that is not 2xx has a [failure document](../../schemas/failure.schema.json) as its body. A client branches
on `reason_code`; the HTTP status is coarse and `reason` is a message for people. `parameters` names the offending query
or path parameter, or the body field by its path (see [Request bodies](#request-bodies)). The codes only the API and `ian serve` use are `not_authenticated`, `host_not_allowed`,
`origin_not_allowed`, `endpoint_not_found`, `refresh_job_not_found`, `refresh_job_running`, `help_term_not_found`,
`help_document_not_found` and `port_unavailable`.

| HTTP status | `reason_code` |
| :--- | :--- |
| 400 | `invalid_parameter`, `host_not_allowed`, `origin_not_allowed` |
| 401 | `not_authenticated` |
| 404 | `analysis_run_not_found`, `watchlist_not_found`, `watchlist_entry_not_found`, `refresh_job_not_found`, `help_term_not_found`, `help_document_not_found`, `endpoint_not_found` |
| 409 | `watchlist_name_conflict`, `stored_selection_unreadable` (an add or a refresh that an unreadable entry of the watchlist refuses), `watchlist_empty` (a watchlist to refresh has no entries), `refresh_job_running` |
| 405 | `endpoint_not_found` (a method the endpoint does not declare, `HEAD` included), with an `Allow` header naming the declared method |
| 503 | `database_busy` |
| 500 | every other code, including every other `database_*` code and `execution_error` |

An unexpected failure, whether in an endpoint or in the checks before it, is `execution_error` with a fixed message and
status 500; its detail goes to the log. `port_unavailable` occurs only
at launch.

When a rule rejected a value (a field of a selection, a blank name), `invalid_parameter` also carries `errors`, one
item for every rejected value in field order, each with its `rule`, `parameters`, `arguments` and `message`; `reason`
and `parameters` are the first item's. A client can place each message on its form field and translate by `rule`. A
rejection that comes from the shape of the request (an unknown field, a wrong type, a bad ID) has `errors` `null`.

A parameter is rejected with `invalid_parameter`, naming it, when it is unknown, when it is given more than once, when it
is malformed (including an ID that is not a UUID in a path, which is never a 404), or when its value is out of range.

## Endpoints

All endpoints sit under `/v1`. A method an endpoint does not declare, `HEAD` included, is answered 405 `endpoint_not_found`.
The endpoints that read use `GET`; the actions are below.

| Path | Query parameters | Response |
| :--- | :--- | :--- |
| `/v1/info` | none | `schema_version`, `api_versions`, `engine_version`, `sec_identity_configured` and `locales`; never the identity itself |
| `/v1/strategies` | none | `schema_version` and `items`, each with `analysis`, `method` and `label` |
| `/v1/watchlists` | none | the watchlist list document |
| `/v1/watchlists/{watchlist_id}` | none | the watchlist document |
| `/v1/runs` | `ticker`, `method_id`, `status`, `refresh_id`, `limit`, `offset` | the runs list document |
| `/v1/runs/{analysis_run_id}` | none | the saved run's own strategy document |
| `/v1/runs/{analysis_run_id}/text` | `mode` (required): `concise`, `details` or `diagnostics` | `schema_version`, `mode` and `text` |
| `/v1/refreshes/{refresh_id}/compare` | none | the runs compare document |
| `/v1/strategies/{method_id}/selection` | none | `schema_version`, `schema` and `defaults` (see [Selection forms](#selection-forms)) |
| `/v1/help` | none | the help index document (see [Help](#help)) |
| `/v1/help/terms/{term_id}` | none | one glossary term |
| `/v1/help/documents/{document_id}` | none | one help document with its sections |
| `/v1/help/references` | none | the term of every value of every code set (see [References](#references)) |
| `/v1/refreshes/{refresh_id}/job` | `after` | the refresh job document (see [Refresh jobs](#refresh-jobs)) |
| `/v1/refreshes/job` | `after` | the latest refresh job document |

On `/v1/runs`, `limit` is 1 to 100 and defaults to 20, and `offset` defaults to 0. `method_id` is the `method` value of
an item in `/v1/strategies` (for example `sma_crossover`). The document says whether more rows follow with `has_more`; there is no total.

### Actions

| Request | Body | Success |
| :--- | :--- | :--- |
| `POST /v1/watchlists` | `name` | 201, the watchlist document |
| `PATCH /v1/watchlists/{watchlist_id}` | `name` | 200, the rename document |
| `DELETE /v1/watchlists/{watchlist_id}` | none | 200, the delete document |
| `POST /v1/watchlists/{watchlist_id}/entries` | `method_id`, `tickers`, `selection` | 200, the watchlist document |
| `DELETE /v1/watchlists/{watchlist_id}/entries/{entry_number}` | none | 200, the removal document |
| `POST /v1/watchlists/{watchlist_id}/remove-tickers` | `tickers` | 200, the removal document |
| `POST /v1/watchlists/{watchlist_id}/remove-method` | `method_id` | 200, the removal document |
| `POST /v1/analyses` | `ticker`, `method_id`, `selection`, `save`, `provider_check` | 200, the analysis document |
| `POST /v1/refreshes` | `watchlist_id` or `entries`, `workers`, `save`, `provider_check` | 202, the refresh job document, with a `Location` header |
| `POST /v1/refreshes/{refresh_id}/job/stop` | none (query: `after`) | 200, the refresh job document |

`entry_number` is 1-based, as the watchlist document's `index` and the command line's `remove-entry` are. The rename,
removal and delete documents hold exactly one of `watchlist` and `unreadable`: an action that committed its change and
then found an entry this version cannot read answers 200 with that entry in `unreadable` (`entry_number`, `ticker`,
`method_id` as stored and a `reason` that names no command). Adding to a watchlist that holds such an entry is refused
with 409 `stored_selection_unreadable` and writes nothing. A delete answers `deleted` true; the command line's
`--missing-ok` has no counterpart, because a missing watchlist is 404.

`POST /v1/analyses` analyzes one ticker under one selection. The ticker is trimmed and upper-cased. `save` is optional
and defaults to `false`; `provider_check` is optional and defaults to the `IAN_PROVIDER_CHECK` choice the server was
launched with, as on the command line. The analysis document holds `schema_version`, `analysis_run_id` (`null` when the
run was not saved), `document` (the strategy's own document, as its command's `--json` writes it) and `text`, with the
same run as `concise`, `details` and `diagnostics` text. A run that is unavailable or failed is still 200, because
`document` reports it.

### Refresh jobs

A refresh runs for minutes, so it is a job: `POST /v1/refreshes` starts one and answers 202 at once, and the client
follows it by polling. The job's ID is the refresh ID that every run it saves carries, so a client can list the saved
runs with `/v1/runs?refresh_id=` and compare them with `/v1/refreshes/{refresh_id}/compare`.

The body names exactly one of `watchlist_id` (a watchlist's ID) and `entries` (a list of `{ticker, method_id, selection}`
for a refresh that belongs to no watchlist; `selection` is read as it is for `POST /v1/analyses`). `workers` is optional
and defaults to 2 (1 to 4), `save` is optional and defaults to `true`, and `provider_check` is optional and defaults to
the choice the server was launched with: the same defaults as `ian refresh`. A watchlist is read once, when the job is
accepted; changes made to it afterwards apply to the next refresh. Every check that can be made before a job runs is made
before the 202, and its failure is the response:

| Status | `reason_code` | Cause |
| :--- | :--- | :--- |
| 400 | `invalid_parameter` | neither or both of `watchlist_id` and `entries`; a bad ID; `workers` outside 1 to 4; an empty list (rule `refresh.entries_empty`); an entry that is rejected, named by its 0-based index and field such as `entries[2].selection.short_window`, every rejected entry being listed in `errors`; an entry that repeats an earlier one, the same ticker with an equal selection (rule `entries.duplicate`) |
| 404 | `watchlist_not_found` | no watchlist has that ID |
| 409 | `watchlist_empty` | the watchlist has no entries |
| 409 | `stored_selection_unreadable` | the watchlist holds an entry this version cannot read |
| 409 | `refresh_job_running` | a job is already running; a server runs one at a time |
| 503 | `database_busy` | the database is busy |

The same ticker with the same method under a different selection is not a duplicate. The 202 carries the job document, as a
poll at `after` 0 would give it (the events recorded so far, normally none), and a `Location` header naming the job's URL. `GET /v1/refreshes/{refresh_id}/job` returns the job (404
`refresh_job_not_found` for an ID the server does not keep), and `GET /v1/refreshes/job` returns the server's latest job,
or 404 `refresh_job_not_found` when it has started none. The server keeps only the latest job: a job that has ended stays
until a new one starts, and then its ID is 404.

The job document is `{schema_version, refresh_id, watchlist_id, state, totals, events, next_after, has_more, summary,
failure}`:

- `state` is one of `running`, `stopping`, `completed`, `stopped` and `failed`; the vocabulary is open, so treat a value
  you do not know as unfinished. `stopping` lasts from a stop request until the job ends. `completed` means every entry
  was started, including a job stopped after its last entry had started. `stopped` means a stop was requested and at
  least one entry was never started. `failed` means a failure after the 202, such as a database that is busy or needs
  attention when the job opens it, an unexpected exception, or an event that could not be built: the job then starts no
  more entries, the ones running finish and are saved, and the events recorded before the failure are kept.
- `watchlist_id` is `null` for a refresh over `entries`.
- `totals` is `{admitted, finished, remaining}`: the jobs started, the jobs finished and the jobs not yet started;
  `remaining` stays above zero after a stop.
- `summary` is the [refresh summary](WORKSPACE.md#refreshing-a-watchlist), provider check included, for `completed` and `stopped`, and
  `null` otherwise. `failure` is a [failure document](#errors) for `failed` and `null` otherwise; the events already
  recorded are kept either way.
- An entry whose analysis failed, or raised, is still a finished entry: the event reports it in `result`, and the job is
  `completed`.

#### Events and polling

Each entry records two events, when it starts and when it finishes. An event has `sequence`, `kind` (`started` or
`finished`), `position`, `ticker`, `method_id`, `result` and `analysis`. `sequence` counts the job's events from 1 in the
order they were recorded. `position` is the entry's 0-based place in the refresh: the same as a saved run's
`batch_position` and as the index in an `entries[i]` error, and not the 1-based `entry_number` of a watchlist. Two entries
for one ticker are told apart by their position. A started event has `result` and `analysis` `null`. A finished event's
`result` is the entry as the refresh summary lists it, and its `analysis` is the document `POST /v1/analyses` returns for
the run, so a client can show a result as soon as it is in; `analysis` is `null` for an entry that raised. The
`provider_check` element inside a finished event's analysis is always `null`, as it is for a stored run read back,
because the refresh sends one provider check after the batch and reports it in `summary`.

`after` is the last `sequence` the client has seen; it is optional and defaults to 0, which returns every event. A
negative or non-integer value is `invalid_parameter`, and a value beyond the last sequence returns no events. The
response holds the events after `after` until adding the next one would take the events past 1,048,576 bytes, and always
holds one when one is waiting, however large. `next_after` is the last sequence returned, or `after` when none is, and
`has_more` says whether recorded events remain: a client polls again with `after` set to `next_after`, at once when
`has_more` is `true` and after a short wait otherwise, until `state` is `completed`, `stopped` or `failed`.

`POST /v1/refreshes/{refresh_id}/job/stop` asks the job to stop starting entries: the entries already running finish and
are saved as usual. It is idempotent, takes the same optional `after` as a poll (a rejected `after` stops nothing), and
answers as a poll does: the job document with the events after `after`, so a client that passes on each answer's
`next_after`, the stop answer's included, sees every event exactly once. Its `state` is `stopping`, or the final state
when the job had already ended. It is 404 `refresh_job_not_found` for an ID the server does not keep. A stop never
fabricates a result for an entry that never started.

#### One job at a time, and one database

A server runs one job at a time: a job is running until its `state` is `completed`, `stopped` or `failed`, and a new job
may start from then on.  Two servers, or a server and the command line, may use one database: SQLite's
write-ahead log and its busy timeout order their writes, and a write that waits too long is `database_busy`. A running
refresh works from the entries it read when it was accepted, so the server's other actions proceed normally while it
runs.

### Request bodies

A body is one JSON object with `Content-Type: application/json`; a field is optional only where the table says so. A
missing or different content type, or a body that is not one JSON object, is `invalid_parameter` with the parameter
`body`. A body is at most 1,048,576 bytes; a larger one, whatever its `Content-Length`, is `invalid_parameter` with the
parameter `body`, as is one holding `NaN`, `Infinity`, `-Infinity` or a number too large to store. An unknown field, a missing field or a field of the wrong type is `invalid_parameter` naming the field by its
path: `name`, `tickers`, `tickers[1]`, `selection.short_window`, `selection.policy.historical_horizon`. In `selection`,
`as_of` is text: `YYYY-MM-DD` (the end of that day, UTC) or an ISO 8601 timestamp with a timezone offset.

### Selection forms

`GET /v1/strategies/{method_id}/selection` returns what a form needs. `schema` is the JSON Schema of the `selection`
fields, the same file as `schemas/selections/<alias>.schema.json`. The schemas state no default for a field the
strategy's settings fill; `defaults` gives the configured value of each, by field name, as it is now, and is an empty
object for a strategy with none. A request that leaves such a field out gets that value. A `method_id` this engine does
not declare is `invalid_parameter` naming `method_id`, as it is anywhere else.

### Help

The engine serves the explanations a client shows beside what it displays, as Markdown. A client renders it with a
sanitizing renderer; the engine never returns HTML.

- `GET /v1/help` returns `schema_version`, `groups` and `documents`. Each group has an `id`, a `title` and its `terms`,
  each with an `id`, a `name` and a short `definition`; each document has an `id` and a `title`. Both lists keep the order
  of the help content.
- `GET /v1/help/terms/{term_id}` returns `schema_version`, `id`, `name`, `definition`, `body` and `group`, which has an
  `id` and a `title`. `body` is empty when an entry is only a definition, so a client renders an empty `body` as nothing.
- `GET /v1/help/documents/{document_id}` returns `schema_version`, `id`, `title`, `introduction` and `sections`, each with
  an `id`, a `heading`, a `level` and its `markdown`, in file order.

Markdown is served as written. A link of the form `help:terms/<term id>` names a term and `help:documents/<document id>`
(with an optional `#<section id>`) names a document or one of its sections; the client turns them into links of its own.
Only a term ID and a document ID are stable references. A group ID and a section ID are valid only within the help
content that carries them, so a client follows them but never stores them. A term ID or document ID the engine does not
have is 404 `help_term_not_found` or `help_document_not_found`; the IDs are plain text in the path and are never
rejected as malformed.

### References

`GET /v1/help/references` returns `schema_version` and `code_sets`: for each code set the API returns, named by its
component in [`schemas/openapi.json`](../../schemas/openapi.json), a map from each value to the ID of the term that
explains it. Keys are sorted by component name, and the values of a set keep the order of the engine's table. Values that
differ only in detail share one term. A label does not appear here: a headline cell, a strategy and a selection field
carry their own `term`. A few fields name no term: `schema_version`, a headline cell's `kind`, the replay text `mode` and
the `method_id` in a path. A client must tolerate a code set or a value it does not know.

### Locales

`locales` in `/v1/info` lists the locales the engine's text is available in, each with a `tag` and a `name` in its own
language, so a client can build a language picker from it. A client states the locale it wants with `Accept-Language`;
the engine honours q-values, matches a tag case-insensitively and falls back from a longer tag to a shorter (`en-CA` to
`en`), and chooses its default locale for `*`, for a header that is absent or malformed, and for a header that names
nothing it has. It never answers 406. Every response states the locale it used in `Content-Language`, and varies on
`Accept-Language`. No document carries a locale field. A preflight may ask for the `Accept-Language` header. Only the
help content follows the locale today; the other text of the API stays in the default locale.

The documents are described by the files in [`schemas/`](../../schemas/) and by
[`schemas/openapi.json`](../../schemas/openapi.json), which also describes the documents only the API serves.
