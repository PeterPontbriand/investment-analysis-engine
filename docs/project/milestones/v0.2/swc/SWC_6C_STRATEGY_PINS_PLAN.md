# SWC.6c — Strategy Pins: Slice Plan

Plans the slice that removes the tests which pin the four production strategies, so the strategy generator's
end-to-end test can run the conformance tests with nothing deselected. The slice sits in the
[SWC sequence](SWC_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status); its decision record is
[B.20](SWC_CONTRACT_AND_SLICE_PLAN.md#b20-swc6b-the-pinned-tests-and-the-new-slice-swc6c-2026-10-18).

## 1. At a glance

- **What this slice does:** makes the 17 accidental pins in [Appendix A](#appendix-a-the-pinned-tests) read
  `STRATEGIES`, `ToolName` or the tiers instead of naming four strategies, and turns the 27 reviewed pins into
  `reviewed` sites in `scripts/strategy_sites.toml`, each with a fill in `tests/scripts/generator_fills/`. It then
  requires the end-to-end test's deselect list to be empty.
- **What it does not do:** change a formula, a classification, a stored shape or production behaviour, or add a
  strategy. It changes tests, the site data file and the end-to-end test's fills.
- **Rules it follows:** a test that can read the descriptors does; a file a new strategy legitimately writes by
  hand becomes a site that the status command checks and the generator's test fills; the end-to-end test stays
  inside the two-minute budget it was given ([B.19](SWC_CONTRACT_AND_SLICE_PLAN.md#b19-swc6-split-and-the-specimen-decisions-2026-10-18)); the
  complete managed gate ends the slice.
- **What waits for it:** SWC.7 and Step 3.5. Until the list is empty a contributor following the guide still has to
  find 44 failing tests by running the whole suite, and the guide's edit-site table is incomplete.
- **Where detail lives:** the tests are in [Appendix A](#appendix-a-the-pinned-tests); the decision is in
  [B.20](SWC_CONTRACT_AND_SLICE_PLAN.md#b20-swc6b-the-pinned-tests-and-the-new-slice-swc6c-2026-10-18).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| SWC.6c | [Make the pins derived, and the reviewed ones sites](#swc6c--strategy-pins) | Next | |

## 3. The slice

### SWC.6c — Strategy pins

- **Problem:** the generator's end-to-end test found 44 tests in 11 files that fail once a fifth
  strategy exists, for reasons no site covers. 17 of them pin the four strategies where they could read the
  descriptors; 27 are content a new strategy writes by hand that the site data file does not list.
- **Decision:** the accidental pins read `STRATEGIES`, `ToolName` or the tiers. Each reviewed pin becomes a
  `reviewed` site (an expected-output file, a snapshot, a per-alias case table or patch table, the per-tool
  dependencies of the registration tests), with a check that finds it done and a fill in the end-to-end test.
  The end-to-end test then deselects nothing, and fails if the list in
  `tests/scripts/generator_fills/deselected.toml` is not empty.
- **Scope:** the 11 test files of the appendix, `scripts/strategy_sites.toml`, `scripts/strategy_conformance.py`
  for the new site checks, `tests/scripts/generator_fills/` and the end-to-end test. The three files that are not
  run whole today (`tests/test_failure_messages.py`, `tests/test_cli_workspace.py` and
  `tests/test_command_validation_failures.py`, about a minute together) are run whole once their pins are gone, so the
  slice re-measures the end-to-end test against its two-minute budget and, if it exceeds it, stops and asks.
- **Branch:** `feat/swc-6c-strategy-pins`, from `main` after SWC.6b has merged.
- **Detail:** [Appendix A](#appendix-a-the-pinned-tests).

## 4. Scope limits and acceptance criteria

- Any change to production behaviour, a formula, a classification or a stored shape.
- A new strategy, or a change to the descriptor's fields.
- Moving a test out of the managed gate to meet the time budget; the slice stops and asks instead.
- Done when `tests/scripts/generator_fills/deselected.toml` has no entry, the end-to-end test passes, the status
  command reports every site done for the throwaway strategy, the guide's generated edit-site table lists the new
  sites, and the complete managed gate passes.

## 5. Background and origin

SWC.6b's end-to-end test copies the repository, generates a throwaway strategy, fills it and runs the conformance
tests. Running the whole suite in the copy gave 48 failures that no fill covered and took about five minutes. The
project owner chose to run a named list of descriptor-derived files, to deselect the pins by node id with a
stale-checked list, to classify each pin, and to plan this slice
([B.20](SWC_CONTRACT_AND_SLICE_PLAN.md#b20-swc6b-the-pinned-tests-and-the-new-slice-swc6c-2026-10-18)). The other
failures of that run were not pins: a source file of the generator counted folders up from itself, the throwaway
guide lacked a watchlist options section, and the repository link check needs a git checkout, which the copy is not.

## Appendix A: The pinned tests

Every test the end-to-end test deselects from the copy, found on 2026-10-18. `accidental` is a test that pins the
four strategies where it could read `STRATEGIES`, `ToolName` or the tiers; `reviewed` is content a new strategy
legitimately writes by hand, such as an expected-output file or a snapshot. The machine-readable list is
`tests/scripts/generator_fills/deselected.toml`, and the end-to-end test fails if a node id here is missing from it
or the other way round.

| Node id | File | Kind | What it pins |
| :--- | :--- | :--- | :--- |
| `tests/test_strategy_wiring_conformance.py::test_aliases_and_method_ids_round_trip_and_an_unknown_one_is_not_a_fallback` | `tests/test_strategy_wiring_conformance.py` | accidental | The alias list of the four production strategies. |
| `tests/test_strategy_wiring_conformance.py::test_t21_every_json_command_has_a_typed_document_and_a_current_schema` | `tests/test_strategy_wiring_conformance.py` | accidental | The count of --json commands, 13. |
| `tests/test_strategy_settings.py::test_the_two_configurable_strategies_declare_their_models` | `tests/test_strategy_settings.py` | accidental | Each of the four strategies' settings model. |
| `tests/test_provider_check_element.py::test_each_strategy_document_accepts_a_check_that_names_its_providers_and_rejects_every_other[ci-probe]` | `tests/test_provider_check_element.py` | reviewed | The per-alias provider-check case table. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[1-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[2-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[3-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[4-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[5-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[6-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[7-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[8-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[11-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[11-save-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[12-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[15-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[16-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_failure_messages.py::test_every_direct_command_gives_every_counterpart_row_its_code_and_message[17-ci-probe]` | `tests/test_failure_messages.py` | reviewed | The per-alias analysis patch for each failure row. |
| `tests/test_cli_workspace.py::test_runs_list_rejects_a_canonical_method_id_or_unknown_alias_as_a_usage_error` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_the_analysis_help_text_names_every_declared_alias_as_before[args0-Method to seed: momentum, graham-number, graham-growth, or fcf-growth.]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_the_analysis_help_text_names_every_declared_alias_as_before[args1-Method: momentum, graham-number, graham-growth, or fcf-growth.]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_the_analysis_help_text_names_every_declared_alias_as_before[args2-Filter by method: momentum, graham-number, graham-growth, or fcf-growth.]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_every_analysis_option_rejects_an_unknown_alias_with_the_same_usage_error[args0]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_every_analysis_option_rejects_an_unknown_alias_with_the_same_usage_error[args1]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_every_analysis_option_rejects_an_unknown_alias_with_the_same_usage_error[args2]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_cli_workspace.py::test_every_analysis_option_rejects_an_unknown_alias_with_the_same_usage_error[args3]` | `tests/test_cli_workspace.py` | accidental | The four aliases in the --analysis help text and the unknown-alias usage error. |
| `tests/test_command_validation_failures.py::test_the_sentence_goes_to_standard_error_and_the_command_exits_1[WRK-1:watchlist create W AAPL -a bogus]` | `tests/test_command_validation_failures.py` | accidental | The four aliases in the unknown-alias sentence. |
| `tests/test_command_validation_failures.py::test_the_sentence_goes_to_standard_error_and_the_command_exits_1[WRK-1:watchlist add-selection W AAPL -a bogus]` | `tests/test_command_validation_failures.py` | accidental | The four aliases in the unknown-alias sentence. |
| `tests/test_command_validation_failures.py::test_the_sentence_goes_to_standard_error_and_the_command_exits_1[WRK-1:watchlist remove-method W -a bogus]` | `tests/test_command_validation_failures.py` | accidental | The four aliases in the unknown-alias sentence. |
| `tests/test_command_validation_failures.py::test_the_sentence_goes_to_standard_error_and_the_command_exits_1[WRK-1:runs list --analysis bogus]` | `tests/test_command_validation_failures.py` | accidental | The four aliases in the unknown-alias sentence. |
| `tests/test_command_validation_failures.py::test_a_command_with_json_writes_one_valid_failure_document_and_nothing_to_standard_error[WRK-1:runs list --analysis bogus]` | `tests/test_command_validation_failures.py` | accidental | The four aliases in the unknown-alias sentence. |
| `tests/test_direct_command_output.py::test_direct_command_output_matches_the_stored_output[ci-probe-text]` | `tests/test_direct_command_output.py` | reviewed | The stored expected output of each direct command. |
| `tests/test_direct_command_output.py::test_direct_command_output_matches_the_stored_output[ci-probe-json]` | `tests/test_direct_command_output.py` | reviewed | The stored expected output of each direct command. |
| `tests/test_cli_help_output.py::test_help_matches_the_stored_output[application]` | `tests/test_cli_help_output.py` | reviewed | The stored help snapshot of the application. |
| `tests/evaluation/test_models.py::test_string_enum_values[ToolName-expected_values1]` | `tests/evaluation/test_models.py` | accidental | The four ToolName values. |
| `tests/orchestrator/test_analysis_tools.py::test_registered_handlers_execute_all_approved_strategies` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_momentum_tool_use_cache_argument_reaches_the_provider[arguments0-True]` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_momentum_tool_use_cache_argument_reaches_the_provider[arguments1-False]` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_registered_handlers_apply_known_etf_policy_without_changing_momentum` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_handler_validation_fails_closed_before_analysis` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_registration_exposes_strict_argument_contracts_and_rejects_duplicates` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_fcf_handler_rejects_a_naive_injected_clock` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/orchestrator/test_analysis_tools.py::test_registration_requires_a_handler_for_every_tool_and_no_other` | `tests/orchestrator/test_analysis_tools.py` | reviewed | The per-tool dependencies the registration tests build. |
| `tests/reporting/test_strategy_documents.py::test_each_stored_document_declares_the_version_of_its_envelope` | `tests/reporting/test_strategy_documents.py` | reviewed | The stored expected document of each strategy. |
