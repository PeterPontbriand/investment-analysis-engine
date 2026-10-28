"""The SEC adapter's settings file: the reviewed ticker-to-CIK overrides a user may set."""

from pydantic import BaseModel, ConfigDict, field_validator

SEC_EDGAR_ALIAS = "sec_edgar"
PROVIDER_SETTINGS_FOLDER = "providers"


class SecEdgarSettings(BaseModel):
    """The validated settings of the SEC adapter.

    The model has no defaults: the ``settings.toml`` beside this module gives every key its shipped value, and the
    user's ``providers/sec_edgar.toml`` may override any of them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker_overrides: dict[str, int | str]
    """``ticker_overrides``: ticker = CIK, each naming the registrant a ticker stands for; the shipped table is empty.

    An override wins over SEC's ticker file, including when the file lists the ticker under several CIKs. A ticker is
    written in any case and a CIK as a number or as digits, and both are stored normalized: upper-case ticker and
    ten-digit CIK.
    """

    @field_validator("ticker_overrides", mode="after")
    @classmethod
    def _normalize(cls, value: dict[str, int | str]) -> dict[str, int | str]:
        """Return the table with upper-case tickers and ten-digit CIKs, refusing an invalid or repeated entry."""
        normalized: dict[str, int | str] = {}
        for ticker, cik in value.items():
            name = ticker.strip().upper()
            digits = str(cik).strip()
            if not name or not digits.isascii() or not digits.isdigit() or int(digits) == 0 or len(digits) > 10:
                raise ValueError(f"the override for {ticker!r} must be a ticker and a CIK of one to ten digits.")
            if name in normalized:
                raise ValueError(f"the ticker {name} is overridden more than once.")
            normalized[name] = digits.zfill(10)
        return normalized
