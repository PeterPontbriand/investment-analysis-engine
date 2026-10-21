"""Every command of the application, found by walking its command tree from the root.

A test that uses this module covers a command added later without being edited. A command is reached through the
``commands`` mapping that a group carries; the root and each group are commands as well, so their help is covered too.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer.main

from investment_analysis_engine.cli import app


@dataclass(frozen=True)
class CommandNode:
    """One command of the tree: the words that select it (empty for the root) and the command object."""

    path: tuple[str, ...]
    command: object

    @property
    def name(self) -> str:
        """Return the words a user types to reach the command, or ``ian`` for the root."""
        return " ".join(("ian", *self.path))


def _walk(command: object, path: tuple[str, ...]) -> list[CommandNode]:
    nodes = [CommandNode(path, command)]
    children: dict[str, object] = getattr(command, "commands", {})
    for name, child in children.items():
        nodes.extend(_walk(child, (*path, name)))
    return nodes


def command_nodes() -> list[CommandNode]:
    """Return the root command, every group and every command, in declaration order."""
    return _walk(typer.main.get_command(app), ())


def help_texts(node: CommandNode) -> list[str]:
    """Return the help a user reads for ``node``: the command's own text and that of each option and argument."""
    texts = [getattr(node.command, "help", None)]
    for parameter in getattr(node.command, "params", ()):
        texts.append(getattr(parameter, "help", None))
    return [text for text in texts if isinstance(text, str)]
