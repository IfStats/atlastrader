from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.enums import Timeframe


class MT5Settings(BaseSettings):
    """MetaTrader 5 connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_MT5_",
        env_file=".env",
        extra="ignore",
    )

    login: int | None = None
    password: str | None = None
    server: str | None = None
    path: str | None = None


class RuntimeSettings(BaseSettings):
    """AtlasTrader application runtime settings."""

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

    @property
    def symbol_list(self) -> list[str]:
        """Return configured symbols as a normalized list."""

        return list(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in self.symbols.split(",")
                if symbol.strip()
            )
        )