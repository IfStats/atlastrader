from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CandidateStrategyStatus(StrEnum):
    """Lifecycle state for a research candidate strategy."""

    REJECTED = "rejected"
    ELIGIBLE_FOR_VALIDATION = (
        "eligible_for_validation"
    )


class CandidateStrategy(BaseModel):
    """Immutable strategy candidate derived from historical evidence."""

    model_config = ConfigDict(
        frozen=True
    )

    id: str
    source_pattern_key: str

    strategy: str
    regime_key: str

    sample_size: int = Field(
        ge=0
    )

    expectancy: Decimal
    win_rate: Decimal

    profit_factor: Decimal | None = None
    payoff_ratio: Decimal | None = None

    status: CandidateStrategyStatus

    rationale: list[str] = Field(
        default_factory=list
    )

    created_at: datetime