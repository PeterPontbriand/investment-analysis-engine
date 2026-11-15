"""The ``ian about --json`` document: the engine's version, installation folder and commit.

It is a report, not the failure envelope: it is written whenever the command runs, and a fact it cannot establish is
null. It carries facts and no instructions.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AboutDocument(BaseModel):
    """What the running engine is: its version and, for a source checkout, where it is and which commit it is at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    engine_version: str = Field(description="The installed version of the engine distribution.")
    installation_folder: str | None = Field(
        description=(
            "The folder of the source checkout the engine runs from, as the platform writes a path; null when the "
            "engine was installed as a package."
        )
    )
    commit: str | None = Field(
        description=(
            "The full 40-character Git commit the installation folder is at; null when there is no installation "
            "folder, the folder is not itself a Git checkout (a folder inside another repository is not one), or "
            "Git is not installed."
        )
    )
    uncommitted_changes: bool | None = Field(
        description=(
            "True when the checkout has changes to tracked files or untracked files that Git does not ignore, "
            "false when it has none; null whenever the commit is null or Git could not report the status."
        )
    )
