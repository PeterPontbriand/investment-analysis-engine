"""The specimen's settings file: the one configured constant of its trivial calculation."""

import math

from pydantic import BaseModel, ConfigDict, StrictFloat, field_validator


class SpecimenSettings(BaseModel):
    """The validated settings of the specimen.

    The model has no defaults: the ``settings.toml`` beside this module gives every key its shipped value, and a
    user's settings file may override any of them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    multiplier: StrictFloat
    """``multiplier``: the factor the calculation scales its input value by; positive."""

    @field_validator("multiplier")
    @classmethod
    def _require_positive_multiplier(cls, value: float) -> float:
        """Require a finite, positive multiplier."""
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be a finite number greater than zero.")
        return value
