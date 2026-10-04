"""The closed unions of the supported strategies' native evidence and persisted selections."""

from typing import Annotated

from pydantic import Field

from src.strategies.fcf_growth.models import FCFEarningsGrowthResult
from src.strategies.fcf_growth.selection import FCFGrowthSelection
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.strategies.momentum.analyzer import MomentumRun
from src.strategies.momentum.selection import MomentumSelection

NativeEvidence = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult
SelectionMember = MomentumSelection | GrahamNumberSelection | GrahamGrowthSelection | FCFGrowthSelection
AnalysisSelection = Annotated[SelectionMember, Field(discriminator="method_id")]
