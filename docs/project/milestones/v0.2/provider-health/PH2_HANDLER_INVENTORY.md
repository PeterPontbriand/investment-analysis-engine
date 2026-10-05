# PH.2 — Provider handler inventory

Every exception handler that turns a provider failure into a generic error, or carries one on without its
class, as of `main` at `a0274ef` (2026-10-04). Owned by
[PH.2](PH_CONTRACT_AND_SLICE_PLAN.md#ph2--provider-failure-classification). Line numbers are for that commit and
will move; the symbol is the stable reference. The list came from an AST scan of `src/` for handlers of
`Exception`, `BaseException`, a bare `except`, and tuples mixing `OSError` with `KeyError`, `TypeError` or
`ValueError`, then each was read.

The three kinds are `unreachable`, `unexpected_response` and `no_data`
([definitions](PH_CONTRACT_AND_SLICE_PLAN.md#ph2--provider-failure-classification)).

## 1. Yahoo (`src/data/yfinance/`)

| File and symbol | Line | Handler today | Disposition |
| :--- | :--- | :--- | :--- |
| `client.py` `YFinanceClient.fetch_data` | 87 | `except Exception` around `yf.download`, re-raised as `DataFetchError("Network transport fault ...")` | **Replace.** Transport, timeout and rate-limit exceptions become `unreachable`; an exception raised while yfinance parses its own response becomes `unexpected_response`. The `None`/empty-frame raise (line 94) becomes `no_data`. New raise sites: a non-`DataFrame` result and missing `Open`/`High`/`Low`/`Close`/`Volume` columns become `unexpected_response`. |
| `client.py` `YFinanceClient.fetch_current_quote` | 143 | `except Exception` around `yf.Ticker(...).fast_info`, re-raised as `DataFetchError("Unable to resolve a current quote ...")` | **Replace.** Transport failures `unreachable`; a missing `last_price` key, `None` or non-numeric value `unexpected_response`. The non-finite or non-positive quote raise (line 150) becomes `unexpected_response`. |
| `client.py` `YFinanceClient.fetch_current_quote` | 141 | `except (KeyError, TypeError)` around the optional `currency` read | **Retain.** An absent optional field is not a failure; the handler is already narrow and returns no currency. |
| `client.py` `YFinanceClient._fetch_metadata_snapshot` | 222 | `except Exception` around `yf.Ticker(...).info`; the failure is memoized per ticker | **Replace.** Classified as above; the memoized value keeps its kind. |
| `client.py` `YFinanceClient._fetch_currency` | 240 | `except Exception`, returns `None` (best-effort enrichment) | **Narrow, keep the behavior.** It must still never invalidate usable price history, so it still returns `None`, but it catches only typed provider failures and logs the kind. A non-provider exception propagates. |
| `financial_facts.py` `YFinanceFinancialFactsAdapter.fetch_facts` | 55 | `except DataFetchError`, re-raised as `FinancialProviderError` with a new sentence | **Carry.** The raised `FinancialProviderError` keeps the original kind and provider identity. |

## 2. SEC EDGAR (`src/data/sec_edgar/`, `src/data/http_json.py`)

| File and symbol | Line | Handler today | Disposition |
| :--- | :--- | :--- | :--- |
| `http_json.py` `fetch_json` | 26 | `except (HTTPError, URLError, TimeoutError, OSError)`, re-raised as `OSError` | **Replace.** HTTP 404 on an addressed document `no_data`; HTTP 403, 429 and 5xx, DNS and connection errors, and timeouts `unreachable`. The distinction survives in the typed failure; the sentence keeps the URL and status. |
| `http_json.py` `fetch_json` | 33 | `except (json.JSONDecodeError, UnicodeDecodeError)`, re-raised as `ValueError` | **Replace.** `unexpected_response`. |
| `financial_facts.py` `SecEdgarFinancialFactsAdapter.fetch_facts` | 512 | `except (KeyError, TypeError, ValueError, OSError)`, re-raised as `FinancialProviderError` | **Replace.** The tuple treats a dropped connection and a missing JSON key alike. Transport failures arrive already typed from `fetch_json` and pass through; `KeyError`, `TypeError` and `ValueError` raised while reading a document become `unexpected_response`. |
| `financial_facts.py` `SecEdgarFinancialFactsAdapter._resolve_cik` | 533 | `except KeyError`, raised as `FinancialProviderError` | **Replace.** A ticker absent from SEC's mapping is `no_data`. |
| `financial_facts.py` `SecEdgarFinancialFactsAdapter.resolve_security_unit` | 304 | `except (OSError, ValueError)`, returns `SecurityUnitResolutionReason.PROVIDER_ERROR` | **Narrow.** Catches typed provider failures only; the reason value is unchanged. A non-provider `ValueError` is a defect and propagates. |
| `financial_facts.py` `SecEdgarFinancialFactsAdapter.create_analysis_snapshot` and `_load_ticker_metadata` | 255, 541 | no handler; they call `fetch_json` directly | **Covered by `fetch_json`.** No change beyond receiving typed failures. |

## 3. Massive

| File and symbol | Line | Handler today | Disposition |
| :--- | :--- | :--- | :--- |
| `massive/client.py` `MassiveClient.fetch_data` | 51 | `except Exception`, re-raised as `DataFetchError` | **Retain.** The method builds a mock frame and calls no service; there is nothing to classify. Recorded so it is not skipped by accident. When a live endpoint replaces it, that work classifies it and adds a check. |
| `massive/financial_facts.py` `MassiveFinancialFactsAdapter.fetch_facts` | 95 | `except (KeyError, TypeError, ValueError, OSError)`, re-raised as `FinancialProviderError` | **Replace**, identically to SEC `fetch_facts`. It uses the shared `fetch_json`, so it is classified even though no health check covers it. |

## 4. Carriers: handlers that keep the class from reaching the envelope

| File and symbol | Line | Handler today | Disposition |
| :--- | :--- | :--- | :--- |
| `financial/resolver.py` `resolve_three_year_average_eps` | 509 | `except FinancialProviderError`, builds a `PROVIDER_ERROR` result with `Provider error: <text>` | **Carry.** The result keeps the kind and provider identity as typed fields; the prose stays as it is. |
| `financial/resolver.py` `_resolve_provider` | 1113 | same | **Carry**, same change. |
| `instrument_profile.py` `complete_security_unit_profile` | 196 | `except Exception`, sets `PROVIDER_ERROR` | **Narrow to typed provider failures** and record the kind in the diagnostic. Other exceptions propagate. |
| `instrument_profile.py` `_resolve_identity_candidate` | 319 | `except Exception`, `PROVIDER_ERROR` diagnostic with no cause | **Narrow** and record the kind, as above. |
| `instrument_profile.py` `_resolve_kind_candidate` | 363 | same | **Narrow** and record the kind. |
| `security_identity.py` `resolve_security_identity` | 134 | `except Exception`, `IdentityResolutionStatus.PROVIDER_ERROR` | **Narrow** and record the kind. |

## 5. Boundaries that stay broad by design

These catch everything on purpose and are not provider adapters. PH.2 changes only what they pass on.

| File and symbol | Line | Why it stays | What changes |
| :--- | :--- | :--- | :--- |
| `src/cli_support.py` `execution_errors` | 196 | The CLI's last boundary; it must turn any exception into a clean exit. SWC.4a replaces its inline chain with the shared classifier. | The classifier maps the three kinds to three reason codes. |
| `src/workspace/refresh.py` `refresh_watchlist` | 259, 279 | One job's failure must never abort the batch. | Each job's `reason_code` comes from the same classifier. |

## 6. Not provider adapters

The other `except Exception` sites in `src/` (telemetry, logging, readiness and repositories, the evaluation
runners, the LLM client and the orchestrator loop) do not call an online data provider and are out of scope.
The Ollama client talks to a local service and is not a provider for this work package.

## 7. Completion test

PH.2 adds a test that scans the provider adapter modules in sections 1 to 3 for `except Exception`,
`except BaseException` and bare `except`, and fails on any handler other than the retained
`MassiveClient.fetch_data` mock, so the broad handlers cannot return.
