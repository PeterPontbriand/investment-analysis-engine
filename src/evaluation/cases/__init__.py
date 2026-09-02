"""Reviewed executable Golden-Suite case definitions."""

from src.evaluation.cases.fcf_earnings_growth import (
    FCF_01,
    FCF_02,
    FCF_03,
    FCF_EARNINGS_GROWTH_CASES,
    FCF_ETF_01,
)
from src.evaluation.cases.graham_growth import GRAHAM_GROWTH_CASES, GRG_01, GRG_ETF_01
from src.evaluation.cases.graham_number import GRA_ETF_01, GRAHAM_NUMBER_CASES, GRN_01, GRN_02, GRN_03
from src.evaluation.cases.graham_resolution import GRAHAM_RESOLUTION_CASES, GRN_04, GRN_05
from src.evaluation.cases.momentum import (
    MOMENTUM_BOUNDARY_CASE,
    MOMENTUM_CASES,
    MOMENTUM_ETF_CASE,
    MOMENTUM_SUCCESS_CASE,
)
from src.evaluation.cases.sec_edgar_fpi import FPI_01, FPI_02, FPI_03, FPI_04, SEC_EDGAR_FPI_CASES

__all__ = [
    "GRAHAM_RESOLUTION_CASES",
    "GRA_ETF_01",
    "GRAHAM_NUMBER_CASES",
    "GRAHAM_GROWTH_CASES",
    "GRN_01",
    "GRN_02",
    "GRN_03",
    "MOMENTUM_BOUNDARY_CASE",
    "MOMENTUM_CASES",
    "MOMENTUM_ETF_CASE",
    "MOMENTUM_SUCCESS_CASE",
    "GRG_01",
    "GRG_ETF_01",
    "GRN_04",
    "GRN_05",
    "FCF_01",
    "FCF_02",
    "FCF_03",
    "FCF_EARNINGS_GROWTH_CASES",
    "FCF_ETF_01",
    "FPI_01",
    "FPI_02",
    "FPI_03",
    "FPI_04",
    "SEC_EDGAR_FPI_CASES",
]
