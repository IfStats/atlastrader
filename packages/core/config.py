from decimal import Decimal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskSettings(BaseSettings):
    """Global risk controls for AtlasTrader."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_file=".env",
        extra="ignore",
    )

    max_risk_per_trade: Decimal = Field(
        default=Decimal("0.01"),
        gt=0,
        le=Decimal("0.05"),
    )

    max_daily_loss: Decimal = Field(
        default=Decimal("0.03"),
        gt=0,
        le=Decimal("0.20"),
    )

    max_open_positions: int = Field(
        default=5,
        ge=1,
        le=100,
    )

    max_portfolio_exposure: Decimal = Field(
        default=Decimal("0.50"),
        gt=0,
        le=Decimal("1.00"),
    )

    min_risk_reward_ratio: Decimal = Field(
        default=Decimal("1.5"),
        gt=0,
    )

    max_spread: Decimal = Field(
        default=Decimal("5.0"),
        gt=0,
    )

    trading_enabled: bool = False


class MT5Settings(BaseSettings):
    """MetaTrader 5 connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MT5_",
        env_file=".env",
        extra="ignore",
    )

    login: int | None = None
    password: str | None = None
    server: str | None = None
    path: str | None = None

    def has_credentials(self) -> bool:
        """Return whether explicit MT5 credentials are configured."""

        return (
            self.login is not None
            and bool(self.password)
            and bool(self.server)
        )


class IntelligenceSettings(BaseSettings):
    """External market-intelligence provider configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_INTELLIGENCE_",
        env_file=".env",
        extra="ignore",
    )

    finnhub_api_key: str | None = None
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    request_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
    )
    retry_backoff_seconds: float = Field(
        default=0.5,
        gt=0,
    )

    def has_finnhub_credentials(self) -> bool:
        """Return whether a Finnhub API key is configured."""

        return bool(self.finnhub_api_key)


class RuntimeSettings(BaseSettings):
    """AtlasTrader application runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_file=".env",
        extra="ignore",
    )

    symbols: str = "XAUUSD"
    initial_balance: Decimal = Field(
        default=Decimal(0),
        ge=0,
    )
    scan_interval_seconds: float = Field(
        default=5.0,
        gt=0,
    )
    timeframe: str = "M5"
    candle_lookback: int = Field(
        default=20,
        ge=2,
    )

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, value: str) -> str:
        """Normalize configured timeframe names."""

        normalized = value.strip().upper()

        aliases = {
            "1M": "M1",
            "1MIN": "M1",
            "5M": "M5",
            "5MIN": "M5",
            "15M": "M15",
            "15MIN": "M15",
            "30M": "M30",
            "30MIN": "M30",
            "1H": "H1",
            "4H": "H4",
            "1D": "D1",
        }

        return aliases.get(normalized, normalized)

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