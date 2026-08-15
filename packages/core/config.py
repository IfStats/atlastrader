from decimal import Decimal

from pydantic import Field
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