from abc import ABC, abstractmethod
from decimal import Decimal

from packages.core.models import Instrument


class PositionSizer(ABC):
    """Calculates order volume from account risk parameters."""

    @abstractmethod
    def calculate_volume(
        self,
        *,
        equity: Decimal,
        risk_percent: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        instrument: Instrument,
    ) -> Decimal:
        """Calculate a normalized order volume."""
        raise NotImplementedError


class DefaultPositionSizer(PositionSizer):
    """Risk-based position sizing implementation."""

    def calculate_volume(
        self,
        *,
        equity: Decimal,
        risk_percent: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        instrument: Instrument,
    ) -> Decimal:
        if equity <= Decimal(0):
            raise ValueError("equity must be greater than zero")

        if risk_percent <= Decimal(0):
            raise ValueError("risk_percent must be greater than zero")

        if entry_price <= Decimal(0):
            raise ValueError("entry_price must be greater than zero")

        if stop_loss_price <= Decimal(0):
            raise ValueError("stop_loss_price must be greater than zero")

        if instrument.contract_size <= Decimal(0):
            raise ValueError("instrument contract_size must be greater than zero")

        stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance <= Decimal(0):
            raise ValueError("stop-loss distance must be greater than zero")

        risk_amount = equity * (risk_percent / Decimal(100))

        raw_volume = risk_amount / (
            stop_distance * instrument.contract_size
        )

        return self._normalize_volume(
            raw_volume,
            instrument,
        )

    @staticmethod
    def _normalize_volume(
        volume: Decimal,
        instrument: Instrument,
    ) -> Decimal:
        if instrument.volume_step <= Decimal(0):
            raise ValueError("instrument volume_step must be greater than zero")

        if instrument.min_volume <= Decimal(0):
            raise ValueError("instrument min_volume must be greater than zero")

        normalized = (
            volume // instrument.volume_step
        ) * instrument.volume_step

        normalized = max(normalized, instrument.min_volume)

        if instrument.volume_precision >= 0:
            normalized = normalized.quantize(
                Decimal(1).scaleb(-instrument.volume_precision)
            )

        return normalized