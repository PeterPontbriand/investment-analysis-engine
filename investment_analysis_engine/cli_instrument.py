"""The ``instrument`` command: show what the engine knows about the instrument a ticker names."""

from typing import Annotated

import typer

from investment_analysis_engine.application.instrument_profiles import get_instrument_profile, lookup_instrument_profile
from investment_analysis_engine.cli_support import application_context, document_json, workspace_failures
from investment_analysis_engine.reporting.documents.instrument_profile import (
    build_instrument_profile_document,
    render_instrument_profile_text,
)

instrument_app = typer.Typer(help="Show what the engine knows about an instrument.")


@instrument_app.command("show")
def instrument_show(
    ticker: Annotated[str, typer.Argument(help="The ticker to show.")],
    *,
    lookup: Annotated[
        bool,
        typer.Option(
            "--lookup",
            help="Look the instrument up with the data providers when the stored details are out of date.",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit the instrument profile document.")] = False,
) -> None:
    """Show the stored details of an instrument, without contacting a data provider.

    With --lookup the details are looked up as an analysis does: the stored ones while they are fresh, otherwise
    from the data providers, and a new lookup is stored.
    """
    with workspace_failures("instrument show", json_output=json_output):
        context = application_context()
        stored = lookup_instrument_profile(context, ticker) if lookup else get_instrument_profile(context, ticker)
        document = build_instrument_profile_document(stored)
    typer.echo(document_json(document) if json_output else render_instrument_profile_text(document))


def register(app: typer.Typer) -> None:
    """Register the ``instrument`` sub-app on the root Typer app."""
    app.add_typer(instrument_app, name="instrument")
