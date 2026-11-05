"""The CLI's side of the automatic provider check: the option choice and the printing of the check's lines.

The check itself runs in ``investment_analysis_engine.application.provider_check``. The probe is built at the
composition root (``investment_analysis_engine.cli``) and reaches a command through the Typer context; this module reads
it from there and pairs it with the command's ``--no-provider-check`` option.
"""

import typer

from investment_analysis_engine.application.provider_check import (
    ProviderCheck,
    ProviderCheckChoice,
    ProviderCheckFindings,
)


def provider_check_choice(context: typer.Context, *, no_provider_check: bool) -> ProviderCheckChoice:
    """Read the probe the composition root put on the Typer context and pair it with the command's option."""
    probe = context.obj if isinstance(context.obj, ProviderCheck) else None
    return ProviderCheckChoice(probe=probe, requested=not no_provider_check)


def echo_provider_check(findings: ProviderCheckFindings, *, err: bool) -> None:
    """Write the provider check lines to the stream the failure text that follows them uses."""
    for line in findings.lines():
        typer.echo(line, err=err)
