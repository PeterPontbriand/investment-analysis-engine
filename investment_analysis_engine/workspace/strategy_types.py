"""The closed unions of the supported strategies' native evidence and persisted selections."""

from typing import Annotated

from pydantic import Field

from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.strategies.momentum.analyzer import MomentumRun
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection

NativeEvidence = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult
SelectionMember = MomentumSelection | GrahamNumberSelection | GrahamGrowthSelection | FCFGrowthSelection
AnalysisSelection = Annotated[SelectionMember, Field(discriminator="method_id")]
