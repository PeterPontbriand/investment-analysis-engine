"""The marker a generated strategy file calls in a body its author has not written yet.

``scripts/new_strategy.py`` writes typed stubs whose unfilled bodies call :func:`unfilled_stub`. The call returns
``NoReturn``, so a stub type-checks as written, and raises :class:`UnfilledStubError` if it is ever reached. The test
suite fails while any such call remains under ``investment_analysis_engine/``, so a file with an unfilled body cannot
merge.
"""

from typing import NoReturn


class UnfilledStubError(NotImplementedError):
    """Raised when a generated body that its author has not written yet is reached."""


def unfilled_stub(site: str) -> NoReturn:
    """Fail because the generated body for ``site`` has not been written.

    Args:
        site: The identifier of the edit site that owns the body, such as ``"codec"``.

    Raises:
        UnfilledStubError: Always.
    """
    raise UnfilledStubError(f"The generated body for the {site!r} site has not been written.")
