from packages.core.models import Instrument


class InstrumentRegistry:
    """Registry of tradable instruments."""

    def __init__(
        self,
        instruments: list[Instrument] | None = None,
    ) -> None:
        self._instruments: dict[str, Instrument] = {}
        self._enabled: set[str] = set()

        for instrument in instruments or []:
            self.register(instrument)

    def register(self, instrument: Instrument) -> None:
        """Register or replace an instrument by symbol."""

        symbol = instrument.symbol.strip()

        if not symbol:
            raise ValueError("Instrument symbol cannot be empty")

        if symbol != instrument.symbol:
            raise ValueError(
                "Instrument symbol cannot contain leading or trailing whitespace"
            )

        self._instruments[symbol] = instrument
        self._enabled.add(symbol)

    def unregister(self, symbol: str) -> None:
        """Remove an instrument from the registry."""

        if symbol not in self._instruments:
            raise KeyError(f"Instrument not found: {symbol}")

        del self._instruments[symbol]
        self._enabled.discard(symbol)

    def get(self, symbol: str) -> Instrument:
        """Return an instrument by symbol."""

        try:
            return self._instruments[symbol]
        except KeyError as exc:
            raise KeyError(
                f"Instrument not found: {symbol}"
            ) from exc

    def contains(self, symbol: str) -> bool:
        """Return whether an instrument is registered."""

        return symbol in self._instruments

    def enable(self, symbol: str) -> None:
        """Enable an instrument for trading."""

        self.get(symbol)
        self._enabled.add(symbol)

    def disable(self, symbol: str) -> None:
        """Disable an instrument for trading."""

        self.get(symbol)
        self._enabled.discard(symbol)

    def is_enabled(self, symbol: str) -> bool:
        """Return whether an instrument is enabled for trading."""

        return symbol in self._enabled

    def tradable(self) -> list[Instrument]:
        """Return all instruments currently enabled for trading."""

        return [
            instrument
            for symbol, instrument in self._instruments.items()
            if symbol in self._enabled
        ]

    def get_by_asset_class(
        self,
        asset_class: str,
    ) -> list[Instrument]:
        """Return instruments matching an asset class."""

        normalized = asset_class.strip().lower()

        if not normalized:
            raise ValueError("asset_class cannot be empty")

        return [
            instrument
            for instrument in self._instruments.values()
            if instrument.asset_class.lower() == normalized
        ]

    def tradable_by_asset_class(
        self,
        asset_class: str,
    ) -> list[Instrument]:
        """Return enabled instruments matching an asset class."""

        normalized = asset_class.strip().lower()

        if not normalized:
            raise ValueError("asset_class cannot be empty")

        return [
            instrument
            for instrument in self.tradable()
            if instrument.asset_class.lower() == normalized
        ]

    def all(self) -> list[Instrument]:
        """Return all registered instruments."""

        return list(self._instruments.values())

    def symbols(self) -> list[str]:
        """Return registered instrument symbols."""

        return list(self._instruments)

    def tradable_symbols(self) -> list[str]:
        """Return symbols currently enabled for trading."""

        return [
            symbol
            for symbol in self._instruments
            if symbol in self._enabled
        ]

    def __len__(self) -> int:
        """Return the number of registered instruments."""

        return len(self._instruments)