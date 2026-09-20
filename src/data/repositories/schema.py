"""Core schema for the Gate D0-approved persistence tables.

UTC/date strings and canonical JSON are validated fully by later adapters.
SQL checks enforce storage shape, enums, identity presence, and simple bounds.
Schema creation and encoding-version seeding belong exclusively to migrations.
"""

import sqlalchemy as sa

metadata = sa.MetaData()

schema_metadata = sa.Table(
    "schema_metadata",
    metadata,
    sa.Column("metadata_key", sa.TEXT(), nullable=False),
    sa.Column("metadata_value", sa.INTEGER(), nullable=False),
    sa.PrimaryKeyConstraint("metadata_key", name="pk_schema_metadata"),
    sa.CheckConstraint("length(trim(metadata_key)) > 0", name="ck_schema_metadata_metadata_key_nonempty"),
    sa.CheckConstraint(
        "typeof(metadata_value) = 'integer' AND metadata_value >= 1", name="ck_schema_metadata_metadata_value_range"
    ),
)

trajectory_events = sa.Table(
    "trajectory_events",
    metadata,
    sa.Column("event_id", sa.TEXT(), nullable=False),
    sa.Column("run_id", sa.TEXT(), nullable=False),
    sa.Column("session_id", sa.TEXT(), nullable=False),
    sa.Column("sequence", sa.INTEGER(), nullable=False),
    sa.Column("timestamp", sa.TEXT(), nullable=False),
    sa.Column("event_type", sa.TEXT(), nullable=False),
    sa.Column("component", sa.TEXT(), nullable=False),
    sa.Column("schema_version", sa.INTEGER(), nullable=False),
    sa.Column("mode", sa.TEXT(), nullable=False),
    sa.Column("span_id", sa.TEXT(), nullable=False),
    sa.Column("parent_span_id", sa.TEXT(), nullable=True),
    sa.Column("model_tag", sa.TEXT(), nullable=True),
    sa.Column("provider", sa.TEXT(), nullable=True),
    sa.Column("step_index", sa.INTEGER(), nullable=True),
    sa.Column("tool_name", sa.TEXT(), nullable=True),
    sa.Column("tool_args_json", sa.TEXT(), nullable=True),
    sa.Column("tool_result_summary_json", sa.TEXT(), nullable=True),
    sa.Column("prompt_tokens", sa.INTEGER(), nullable=True),
    sa.Column("completion_tokens", sa.INTEGER(), nullable=True),
    sa.Column("latency_ms", sa.REAL(), nullable=True),
    sa.Column("payload_json", sa.TEXT(), nullable=True),
    sa.Column("payload_hash", sa.TEXT(), nullable=True),
    sa.Column("error_json", sa.TEXT(), nullable=True),
    sa.PrimaryKeyConstraint("event_id", name="pk_trajectory_events"),
    sa.UniqueConstraint("run_id", "sequence", name="uq_trajectory_events_1"),
    sa.CheckConstraint("length(trim(event_id)) > 0", name="ck_trajectory_events_event_id_nonempty"),
    sa.CheckConstraint("length(trim(run_id)) > 0", name="ck_trajectory_events_run_id_nonempty"),
    sa.CheckConstraint("length(trim(session_id)) > 0", name="ck_trajectory_events_session_id_nonempty"),
    sa.CheckConstraint("typeof(sequence) = 'integer' AND sequence >= 1", name="ck_trajectory_events_sequence_range"),
    sa.CheckConstraint(
        (
            "length(timestamp) = 27 AND timestamp GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(timestamp) IS NOT NULL"
        ),
        name="ck_trajectory_events_timestamp_utc",
    ),
    sa.CheckConstraint(
        "typeof(schema_version) = 'integer' AND schema_version >= 1", name="ck_trajectory_events_schema_version_range"
    ),
    sa.CheckConstraint("length(trim(span_id)) > 0", name="ck_trajectory_events_span_id_nonempty"),
    sa.CheckConstraint(
        "step_index IS NULL OR (typeof(step_index) = 'integer' AND step_index >= 1)",
        name="ck_trajectory_events_step_index_range",
    ),
    sa.CheckConstraint(
        "prompt_tokens IS NULL OR (typeof(prompt_tokens) = 'integer' AND prompt_tokens >= 0)",
        name="ck_trajectory_events_prompt_tokens_range",
    ),
    sa.CheckConstraint(
        ("completion_tokens IS NULL OR (typeof(completion_tokens) = 'integer' AND completion_tokens >= 0)"),
        name="ck_trajectory_events_completion_tokens_range",
    ),
    sa.CheckConstraint(
        (
            "event_type IN ('run_start', 'step_start', 'prompt_sent', 'llm_response', "
            "'tool_call', 'tool_result', 'error', 'recovery_attempted', 'step_end', "
            "'run_end')"
        ),
        name="ck_trajectory_events_event_type_enum",
    ),
    sa.CheckConstraint("mode IN ('light', 'full')", name="ck_trajectory_events_mode_enum"),
    sa.CheckConstraint("latency_ms >= 0", name="ck_trajectory_events_latency_nonnegative"),
)

resolved_input_cache = sa.Table(
    "resolved_input_cache",
    metadata,
    sa.Column("cache_key", sa.TEXT(), nullable=False),
    sa.Column("subject_kind", sa.TEXT(), nullable=False),
    sa.Column("subject_id", sa.TEXT(), nullable=False),
    sa.Column("field_name", sa.TEXT(), nullable=False),
    sa.Column("basis", sa.TEXT(), nullable=True),
    sa.Column("provider_id", sa.TEXT(), nullable=False),
    sa.Column("analysis_as_of", sa.TEXT(), nullable=True),
    sa.Column("schema_version", sa.INTEGER(), nullable=False),
    sa.Column("key_period_start", sa.TEXT(), nullable=True),
    sa.Column("key_period_end", sa.TEXT(), nullable=True),
    sa.Column("cached_at", sa.TEXT(), nullable=False),
    sa.Column("value", sa.REAL(), nullable=False),
    sa.Column("source_kind", sa.TEXT(), nullable=False),
    sa.Column("resolved_at", sa.TEXT(), nullable=False),
    sa.Column("units", sa.TEXT(), nullable=True),
    sa.Column("currency", sa.TEXT(), nullable=True),
    sa.Column("input_provider_id", sa.TEXT(), nullable=True),
    sa.Column("provider_field", sa.TEXT(), nullable=True),
    sa.Column("input_period_start", sa.TEXT(), nullable=True),
    sa.Column("input_period_end", sa.TEXT(), nullable=True),
    sa.Column("observed_at", sa.TEXT(), nullable=True),
    sa.Column("available_at", sa.TEXT(), nullable=True),
    sa.Column("retrieved_at", sa.TEXT(), nullable=True),
    sa.Column("lineage_json", sa.TEXT(), nullable=True),
    sa.Column("notes_json", sa.TEXT(), nullable=False),
    sa.Column("fiscal_year", sa.INTEGER(), nullable=True),
    sa.Column("period_kind", sa.TEXT(), nullable=True),
    sa.Column("accounting_scope", sa.TEXT(), nullable=True),
    sa.Column("capital_expenditure_sign", sa.TEXT(), nullable=True),
    sa.Column("provider_fact_id", sa.TEXT(), nullable=True),
    sa.PrimaryKeyConstraint("cache_key", name="pk_resolved_input_cache"),
    sa.CheckConstraint("length(trim(cache_key)) > 0", name="ck_resolved_input_cache_cache_key_nonempty"),
    sa.CheckConstraint("length(trim(subject_id)) > 0", name="ck_resolved_input_cache_subject_id_nonempty"),
    sa.CheckConstraint("length(trim(field_name)) > 0", name="ck_resolved_input_cache_field_name_nonempty"),
    sa.CheckConstraint("basis IS NULL OR (length(trim(basis)) > 0)", name="ck_resolved_input_cache_basis_nonempty"),
    sa.CheckConstraint("length(trim(provider_id)) > 0", name="ck_resolved_input_cache_provider_id_nonempty"),
    sa.CheckConstraint(
        (
            "analysis_as_of IS NULL OR (length(analysis_as_of) = 27 AND analysis_as_of GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(analysis_as_of) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_analysis_as_of_utc",
    ),
    sa.CheckConstraint(
        "typeof(schema_version) = 'integer' AND schema_version >= 1",
        name="ck_resolved_input_cache_schema_version_range",
    ),
    sa.CheckConstraint(
        (
            "key_period_start IS NULL OR (length(key_period_start) = 27 AND key_period_start "
            "GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(key_period_start) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_key_period_start_utc",
    ),
    sa.CheckConstraint(
        (
            "key_period_end IS NULL OR (length(key_period_end) = 27 AND key_period_end GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(key_period_end) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_key_period_end_utc",
    ),
    sa.CheckConstraint(
        (
            "length(cached_at) = 27 AND cached_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(cached_at) IS NOT NULL"
        ),
        name="ck_resolved_input_cache_cached_at_utc",
    ),
    sa.CheckConstraint(
        (
            "length(resolved_at) = 27 AND resolved_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(resolved_at) IS NOT NULL"
        ),
        name="ck_resolved_input_cache_resolved_at_utc",
    ),
    sa.CheckConstraint(
        (
            "input_period_start IS NULL OR (length(input_period_start) = 27 AND "
            "input_period_start GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(input_period_start) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_input_period_start_utc",
    ),
    sa.CheckConstraint(
        (
            "input_period_end IS NULL OR (length(input_period_end) = 27 AND input_period_end "
            "GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(input_period_end) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_input_period_end_utc",
    ),
    sa.CheckConstraint(
        (
            "observed_at IS NULL OR (length(observed_at) = 27 AND observed_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(observed_at) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_observed_at_utc",
    ),
    sa.CheckConstraint(
        (
            "available_at IS NULL OR (length(available_at) = 27 AND available_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(available_at) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_available_at_utc",
    ),
    sa.CheckConstraint(
        (
            "retrieved_at IS NULL OR (length(retrieved_at) = 27 AND retrieved_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(retrieved_at) IS NOT NULL)"
        ),
        name="ck_resolved_input_cache_retrieved_at_utc",
    ),
    sa.CheckConstraint(
        "fiscal_year IS NULL OR (typeof(fiscal_year) = 'integer' AND fiscal_year >= 1)",
        name="ck_resolved_input_cache_fiscal_year_range",
    ),
    sa.CheckConstraint("subject_kind IN ('security', 'macro')", name="ck_resolved_input_cache_subject_kind_enum"),
    sa.CheckConstraint("source_kind IN ('provider', 'derived')", name="ck_resolved_input_cache_source_kind_enum"),
    sa.CheckConstraint(
        "period_kind IN ('completed_annual', 'quarterly', 'ttm')", name="ck_resolved_input_cache_period_kind_enum"
    ),
    sa.CheckConstraint(
        "accounting_scope IN ('consolidated', 'parent', 'segment')",
        name="ck_resolved_input_cache_accounting_scope_enum",
    ),
    sa.CheckConstraint(
        "capital_expenditure_sign IN ('positive_expenditure', 'negative_cash_outflow')",
        name="ck_resolved_input_cache_capital_expenditure_sign_enum",
    ),
    sa.CheckConstraint(
        (
            "(key_period_start IS NULL AND key_period_end IS NULL) OR (key_period_start IS "
            "NOT NULL AND key_period_end IS NOT NULL AND key_period_start <= key_period_end)"
        ),
        name="ck_resolved_input_cache_paired_key_period",
    ),
)

market_data_cache_entries = sa.Table(
    "market_data_cache_entries",
    metadata,
    sa.Column("entry_key", sa.TEXT(), nullable=False),
    sa.Column("ticker", sa.TEXT(), nullable=False),
    sa.Column("request_provider_id", sa.TEXT(), nullable=False),
    sa.Column("request_start", sa.TEXT(), nullable=False),
    sa.Column("request_end", sa.TEXT(), nullable=True),
    sa.Column("request_variant", sa.TEXT(), nullable=False),
    sa.Column("schema_version", sa.INTEGER(), nullable=False),
    sa.Column("cached_at", sa.TEXT(), nullable=False),
    sa.Column("fetch_completed_at", sa.TEXT(), nullable=True),
    sa.Column("row_count", sa.INTEGER(), nullable=False),
    sa.Column("frame_metadata_json", sa.TEXT(), nullable=False),
    sa.Column("context_provider_id", sa.TEXT(), nullable=True),
    sa.Column("observation_interval", sa.TEXT(), nullable=True),
    sa.Column("data_as_of", sa.TEXT(), nullable=True),
    sa.Column("currency", sa.TEXT(), nullable=True),
    sa.Column("observation_count", sa.INTEGER(), nullable=True),
    sa.Column("price_adjustment", sa.TEXT(), nullable=True),
    sa.PrimaryKeyConstraint("entry_key", name="pk_market_data_cache_entries"),
    sa.CheckConstraint("length(trim(entry_key)) > 0", name="ck_market_data_cache_entries_entry_key_nonempty"),
    sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_market_data_cache_entries_ticker_nonempty"),
    sa.CheckConstraint(
        "length(trim(request_provider_id)) > 0", name="ck_market_data_cache_entries_request_provider_id_nonempty"
    ),
    sa.CheckConstraint(
        (
            "length(request_start) = 10 AND request_start GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date(request_start) IS NOT NULL"
        ),
        name="ck_market_data_cache_entries_request_start_date",
    ),
    sa.CheckConstraint(
        (
            "request_end IS NULL OR (length(request_end) = 10 AND request_end GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date(request_end) IS NOT NULL)"
        ),
        name="ck_market_data_cache_entries_request_end_date",
    ),
    sa.CheckConstraint(
        "length(trim(request_variant)) > 0", name="ck_market_data_cache_entries_request_variant_nonempty"
    ),
    sa.CheckConstraint(
        "typeof(schema_version) = 'integer' AND schema_version >= 1",
        name="ck_market_data_cache_entries_schema_version_range",
    ),
    sa.CheckConstraint(
        (
            "length(cached_at) = 27 AND cached_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(cached_at) IS NOT NULL"
        ),
        name="ck_market_data_cache_entries_cached_at_utc",
    ),
    sa.CheckConstraint(
        (
            "fetch_completed_at IS NULL OR (length(fetch_completed_at) = 27 AND "
            "fetch_completed_at GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-"
            "9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(fetch_completed_at) IS NOT NULL)"
        ),
        name="ck_market_data_cache_entries_fetch_completed_at_utc",
    ),
    sa.CheckConstraint(
        "typeof(row_count) = 'integer' AND row_count >= 1", name="ck_market_data_cache_entries_row_count_range"
    ),
    sa.CheckConstraint(
        (
            "data_as_of IS NULL OR (length(data_as_of) = 10 AND data_as_of GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date(data_as_of) IS NOT NULL)"
        ),
        name="ck_market_data_cache_entries_data_as_of_date",
    ),
    sa.CheckConstraint(
        ("observation_count IS NULL OR (typeof(observation_count) = 'integer' AND observation_count >= 0)"),
        name="ck_market_data_cache_entries_observation_count_range",
    ),
    sa.CheckConstraint(
        "request_end IS NULL OR request_start <= request_end", name="ck_market_data_cache_entries_request_bounds"
    ),
)

market_price_observations = sa.Table(
    "market_price_observations",
    metadata,
    sa.Column("entry_key", sa.TEXT(), nullable=False),
    sa.Column("row_position", sa.INTEGER(), nullable=False),
    sa.Column("index_value", sa.TEXT(), nullable=False),
    sa.Column("open", sa.REAL(), nullable=True),
    sa.Column("high", sa.REAL(), nullable=True),
    sa.Column("low", sa.REAL(), nullable=True),
    sa.Column("close", sa.REAL(), nullable=False),
    sa.Column("adj_close", sa.REAL(), nullable=True),
    sa.Column("volume", sa.NUMERIC(asdecimal=False), nullable=True),
    sa.PrimaryKeyConstraint("entry_key", "row_position", name="pk_market_price_observations"),
    sa.UniqueConstraint("entry_key", "index_value", name="uq_market_price_observations_1"),
    sa.ForeignKeyConstraint(
        ["entry_key"],
        ["market_data_cache_entries.entry_key"],
        ondelete="CASCADE",
        name="fk_market_price_observations_entry_key",
    ),
    sa.CheckConstraint("length(trim(entry_key)) > 0", name="ck_market_price_observations_entry_key_nonempty"),
    sa.CheckConstraint(
        "typeof(row_position) = 'integer' AND row_position >= 0", name="ck_market_price_observations_row_position_range"
    ),
    sa.CheckConstraint("length(trim(index_value)) > 0", name="ck_market_price_observations_index_value_nonempty"),
)

watchlists = sa.Table(
    "watchlists",
    metadata,
    sa.Column("watchlist_id", sa.TEXT(), nullable=False),
    sa.Column("normalized_name", sa.TEXT(), nullable=False),
    sa.Column("display_name", sa.TEXT(), nullable=False),
    sa.Column("created_at", sa.TEXT(), nullable=False),
    sa.Column("updated_at", sa.TEXT(), nullable=True),
    sa.PrimaryKeyConstraint("watchlist_id", name="pk_watchlists"),
    sa.UniqueConstraint("normalized_name", name="uq_watchlists_1"),
    sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlists_watchlist_id_nonempty"),
    sa.CheckConstraint("length(trim(normalized_name)) > 0", name="ck_watchlists_normalized_name_nonempty"),
    sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_watchlists_display_name_nonempty"),
    sa.CheckConstraint(
        "length(created_at) = 27 AND created_at GLOB "
        "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
        "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(created_at) IS NOT NULL",
        name="ck_watchlists_created_at_utc",
    ),
    sa.CheckConstraint(
        "updated_at IS NULL OR (length(updated_at) = 27 AND updated_at GLOB "
        "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
        "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(updated_at) IS NOT NULL)",
        name="ck_watchlists_updated_at_utc",
    ),
    sa.CheckConstraint("updated_at IS NULL OR updated_at >= created_at", name="ck_watchlists_timestamp_order"),
)

watchlist_entries = sa.Table(
    "watchlist_entries",
    metadata,
    sa.Column("watchlist_id", sa.TEXT(), nullable=False),
    sa.Column("position", sa.INTEGER(), nullable=False),
    sa.Column("ticker", sa.TEXT(), nullable=False),
    sa.Column("method_id", sa.TEXT(), nullable=False),
    sa.Column("config_schema_version", sa.INTEGER(), nullable=False),
    sa.Column("selection_json", sa.TEXT(), nullable=False),
    sa.PrimaryKeyConstraint("watchlist_id", "position", name="pk_watchlist_entries"),
    sa.ForeignKeyConstraint(
        ["watchlist_id"], ["watchlists.watchlist_id"], ondelete="CASCADE", name="fk_watchlist_entries_watchlist_id"
    ),
    sa.CheckConstraint("length(trim(watchlist_id)) > 0", name="ck_watchlist_entries_watchlist_id_nonempty"),
    sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_watchlist_entries_ticker_nonempty"),
    sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_watchlist_entries_method_id_nonempty"),
    sa.CheckConstraint("typeof(position) = 'integer' AND position >= 0", name="ck_watchlist_entries_position_range"),
    sa.CheckConstraint(
        "typeof(config_schema_version) = 'integer' AND config_schema_version >= 1",
        name="ck_watchlist_entries_config_schema_version_range",
    ),
    sa.CheckConstraint(
        "json_valid(selection_json) AND json_type(selection_json) = 'object'",
        name="ck_watchlist_entries_selection_json_object",
    ),
)

analysis_runs = sa.Table(
    "analysis_runs",
    metadata,
    sa.Column("analysis_run_id", sa.TEXT(), nullable=False),
    sa.Column("refresh_id", sa.TEXT(), nullable=True),
    sa.Column("batch_position", sa.INTEGER(), nullable=True),
    sa.Column("ticker", sa.TEXT(), nullable=False),
    sa.Column("analysis_id", sa.TEXT(), nullable=False),
    sa.Column("method_id", sa.TEXT(), nullable=False),
    sa.Column("outcome", sa.TEXT(), nullable=False),
    sa.Column("completed_at", sa.TEXT(), nullable=False),
    sa.Column("run_schema_version", sa.INTEGER(), nullable=False),
    sa.Column("config_schema_version", sa.INTEGER(), nullable=False),
    sa.Column("method_version", sa.INTEGER(), nullable=False),
    sa.Column("result_schema_version", sa.INTEGER(), nullable=False),
    sa.Column("evidence_codec_version", sa.INTEGER(), nullable=False),
    sa.Column("projection_version", sa.INTEGER(), nullable=False),
    sa.Column("envelope_json", sa.TEXT(), nullable=False),
    sa.PrimaryKeyConstraint("analysis_run_id", name="pk_analysis_runs"),
    sa.CheckConstraint("length(trim(analysis_run_id)) > 0", name="ck_analysis_runs_analysis_run_id_nonempty"),
    sa.CheckConstraint(
        "refresh_id IS NULL OR length(trim(refresh_id)) > 0", name="ck_analysis_runs_refresh_id_nonempty"
    ),
    sa.CheckConstraint("length(trim(ticker)) > 0", name="ck_analysis_runs_ticker_nonempty"),
    sa.CheckConstraint("length(trim(analysis_id)) > 0", name="ck_analysis_runs_analysis_id_nonempty"),
    sa.CheckConstraint("length(trim(method_id)) > 0", name="ck_analysis_runs_method_id_nonempty"),
    sa.CheckConstraint(
        "outcome IN ('completed', 'unavailable', 'not_applicable', 'failed', 'cancelled')",
        name="ck_analysis_runs_outcome_enum",
    ),
    sa.CheckConstraint(
        "length(completed_at) = 27 AND completed_at GLOB "
        "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]."
        "[0-9][0-9][0-9][0-9][0-9][0-9]Z' AND datetime(completed_at) IS NOT NULL",
        name="ck_analysis_runs_completed_at_utc",
    ),
    sa.CheckConstraint(
        "(refresh_id IS NULL AND batch_position IS NULL) OR "
        "(refresh_id IS NOT NULL AND typeof(batch_position) = 'integer' AND batch_position >= 0)",
        name="ck_analysis_runs_refresh_position_pair",
    ),
    *(
        sa.CheckConstraint(f"typeof({field}) = 'integer' AND {field} >= 1", name=f"ck_analysis_runs_{field}_range")
        for field in (
            "run_schema_version",
            "config_schema_version",
            "method_version",
            "result_schema_version",
            "evidence_codec_version",
            "projection_version",
        )
    ),
    sa.CheckConstraint(
        "json_valid(envelope_json) AND json_type(envelope_json) = 'object'",
        name="ck_analysis_runs_envelope_json_object",
    ),
)

sa.Index("ix_trajectory_events_1", trajectory_events.c.session_id, trajectory_events.c.timestamp)
sa.Index(
    "ix_resolved_input_cache_1",
    resolved_input_cache.c.subject_kind,
    resolved_input_cache.c.subject_id,
    resolved_input_cache.c.field_name,
    resolved_input_cache.c.basis,
    resolved_input_cache.c.provider_id,
    resolved_input_cache.c.analysis_as_of,
    resolved_input_cache.c.schema_version,
    resolved_input_cache.c.key_period_end,
    resolved_input_cache.c.key_period_start,
)
sa.Index("ix_analysis_runs_ticker", analysis_runs.c.ticker)
sa.Index("ix_analysis_runs_method_id", analysis_runs.c.method_id)
sa.Index("ix_analysis_runs_outcome", analysis_runs.c.outcome)
sa.Index("ix_analysis_runs_completed", analysis_runs.c.completed_at, analysis_runs.c.analysis_run_id)
sa.Index("ix_analysis_runs_refresh", analysis_runs.c.refresh_id, analysis_runs.c.batch_position)
