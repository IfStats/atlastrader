from decimal import Decimal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.config import MT5Settings as CanonicalMT5Settings
from packages.core.enums import Timeframe


class MT5Settings(CanonicalMT5Settings):
    """Compatibility interface for legacy MT5 settings imports."""


class RuntimeSettings(BaseSettings):
    """Legacy-compatible AtlasTrader runtime settings."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_file=".env",
        extra="ignore",
    )

    symbols: str = "XAUUSD"
    timeframe: Timeframe = Timeframe.M5
    candle_lookback: int = Field(default=20, ge=2)
    interval_seconds: float = Field(default=5.0, gt=0)
    initial_balance: Decimal = Field(
        default=Decimal(0),
        ge=0,
    )

    @field_validator("timeframe", mode="before")
    @classmethod
    def normalize_timeframe(
        cls,
        value: Timeframe | str,
    ) -> Timeframe:
        """Accept canonical enum values and legacy timeframe names."""

        if isinstance(value, Timeframe):
            return value

        normalized = value.strip().upper()

        aliases = {
            "M1": Timeframe.M1,
            "1M": Timeframe.M1,
            "M5": Timeframe.M5,
            "5M": Timeframe.M5,
            "M15": Timeframe.M15,
            "15M": Timeframe.M15,
            "M30": Timeframe.M30,
            "30M": Timeframe.M30,
            "H1": Timeframe.H1,
            "1H": Timeframe.H1,
            "H4": Timeframe.H4,
            "4H": Timeframe.H4,
            "D1": Timeframe.D1,
            "1D": Timeframe.D1,
        }

        try:
            return aliases[normalized]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported timeframe: {value}"
            ) from exc

    @property
    def symbol_list(self) -> list[str]:
        """Return configured symbols as a normalized list."""

        return self.get_symbols()

    def get_symbols(self) -> list[str]:
        """Return normalized, deduplicated trading symbols."""

        symbols = [
            symbol.strip().upper()
            for symbol in self.symbols.split(",")
            if symbol.strip()
        ]

        if not symbols:
            raise ValueError(
                "No trading symbols configured"
            )

        return list(dict.fromkeys(symbols))