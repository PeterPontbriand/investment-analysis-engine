"""Configuration for the graham_number strategy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, StrictFloat


class GrahamNumberConfig(BaseModel):
    """Graham Number request; its EPS is always the three-year average of fiscal EPS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eps_override: StrictFloat | None = None
    quote_override: StrictFloat | None = None
    bvps_override: StrictFloat | None = None
