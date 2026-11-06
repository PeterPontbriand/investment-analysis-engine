"""Shared base for the workspace selection snapshots."""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, field_validator


class SelectionRuleError(ValueError):
    """A selection rule a field value broke, in a form a caller can spell in its own names and translate.

    The message is a template: each field the rule names is written ``{field}`` (a nested field by its dotted
    name, ``{policy.historical_horizon}``) and each value ``{field_value}`` or another declared argument name.
    A caller fills in its own name for each field, so the command line shows an option where the API shows a field.

    Attributes:
        template: The message with its placeholders.
        fields: The model fields the rule names.
        rule: The stable identifier of the rule, ``<alias>.<rule>`` such as ``momentum.window_order``.
        arguments: The values the template shows, by placeholder name.
    """

    def __init__(
        self,
        template: str,
        *,
        fields: Sequence[str],
        rule: str,
        arguments: Mapping[str, object] | None = None,
    ) -> None:
        """Keep the template, the fields it names, the rule identifier and the values it shows."""
        super().__init__(template)
        self.template = template
        self.fields: tuple[str, ...] = tuple(fields)
        self.rule = rule
        self.arguments: dict[str, object] = dict(arguments or {})


class FrozenSelection(BaseModel):
    """Shared strictness for workspace selection snapshots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("config_schema_version", mode="before", check_fields=False)
    @classmethod
    def _require_integer_version(cls, value: object) -> object:
        """Reject boolean/float lookalikes before validating the version literal."""
        if type(value) is not int:
            raise ValueError("config_schema_version must be an integer.")
        return value
