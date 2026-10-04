"""Reviewed executable Golden-Suite case definitions, one module per strategy."""

from src.evaluation.cases.fcf_growth import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_ETF_01,
    FCF_GROWTH_ARGUMENTS,
    FCF_GROWTH_CASES,
    FPI_03,
)
from src.evaluation.cases.graham_growth import (
    FPI_01,
    FPI_02,
    FPI_04,
    GRAHAM_GROWTH_ARGUMENTS,
    GRAHAM_GROWTH_CASES,
    GRG_01,
    GRG_ETF_01,
)
from src.evaluation.cases.graham_number import (
    GRA_ETF_01,
    GRAHAM_NUMBER_ARGUMENTS,
    GRAHAM_NUMBER_CASES,
    GRN_01,
    GRN_02,
    GRN_03,
    GRN_04,
    GRN_05,
)
from src.evaluation.cases.momentum import (
    MOMENTUM_ARGUMENTS,
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_CASES,
    MOMENTUM_ETF_CASE,
    MOMENTUM_SUCCESS_CASE,
)

__all__ = [
    "FCF_01",
    "FCF_02",
    "FCF_03",
    "FCF_ETF_01",
    "FCF_GROWTH_ARGUMENTS",
    "FCF_GROWTH_CASES",
    "FPI_01",
    "FPI_02",
    "FPI_03",
    "FPI_04",
    "GRAHAM_GROWTH_ARGUMENTS",
    "GRAHAM_GROWTH_CASES",
    "GRAHAM_NUMBER_ARGUMENTS",
    "GRAHAM_NUMBER_CASES",
    "GRA_ETF_01",
    "GRG_01",
    "GRG_ETF_01",
    "GRN_01",
    "GRN_02",
    "GRN_03",
    "GRN_04",
    "GRN_05",
    "MOMENTUM_ARGUMENTS",
    "MOMENTUM_BOUNDARY_CASE",
    "MOMENTUM_CASES",
    "MOMENTUM_ETF_CASE",
    "MOMENTUM_SUCCESS_CASE",
]
