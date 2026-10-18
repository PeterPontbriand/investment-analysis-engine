"""The specimen's catalog: the case tuple the specimen's tests run."""

from typing import Final

from tests.specimen.cases import SPECIMEN_CASES

CATALOG_CASE_IDS: Final = tuple(case.case_id for case in SPECIMEN_CASES)
"""The ids of the catalog's cases, in order; ``tests/test_specimen_strategy.py`` pins them."""
