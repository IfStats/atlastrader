from abc import ABC, abstractmethod

from packages.core.trading_journal import TradeDecision, TradeOutcome


class TradeJournal(ABC):
    """Interface for recording and retrieving trading decisions and outcomes."""

    @abstractmethod
    def record_decision(self, decision: TradeDecision) -> None:
        """Record a trade decision."""
        ...

    @abstractmethod
    def record_outcome(self, outcome: TradeOutcome) -> None:
        """Record a trade outcome."""
        ...

    @abstractmethod
    def update_outcome(self, outcome: TradeOutcome) -> None:
        """Update an existing trade outcome."""
        ...

    @abstractmethod
    def get_decision(self, decision_id: str) -> TradeDecision | None:
        """Return a recorded decision by ID."""
        ...

    @abstractmethod
    def get_outcome(self, trade_id: str) -> TradeOutcome | None:
        """Return a recorded outcome by trade ID."""
        ...


class InMemoryTradeJournal(TradeJournal):
    """In-memory journal implementation for development and testing."""

    def __init__(self) -> None:
        self._decisions: dict[str, TradeDecision] = {}
        self._outcomes: dict[str, TradeOutcome] = {}

    def record_decision(self, decision: TradeDecision) -> None:
        if decision.id in self._decisions:
            raise ValueError(f"Decision already recorded: {decision.id}")
        self._decisions[decision.id] = decision

    def record_outcome(self, outcome: TradeOutcome) -> None:
        if outcome.trade_id in self._outcomes:
            raise ValueError(f"Outcome already recorded: {outcome.trade_id}")
        self._outcomes[outcome.trade_id] = outcome

    def update_outcome(self, outcome: TradeOutcome) -> None:
        if outcome.trade_id not in self._outcomes:
            raise ValueError(
                f"Cannot update: Outcome not found for {outcome.trade_id}"
            )
        self._outcomes[outcome.trade_id] = outcome

    def get_decision(self, decision_id: str) -> TradeDecision | None:
        return self._decisions.get(decision_id)

    def get_outcome(self, trade_id: str) -> TradeOutcome | None:
        return self._outcomes.get(trade_id)