from datetime import UTC, datetime
from decimal import Decimal

import MetaTrader5 as mt5  # type: ignore[import-untyped]

from packages.core.enums import (
    AssetClass,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
)
from packages.core.models import Instrument, Order, Position
from packages.execution.interfaces import ExecutionProvider


class MT5ExecutionProvider(ExecutionProvider):
    """MetaTrader 5 execution provider for AtlasTrader."""

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        path: str | None = None,
    ) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self._connected = False

    async def connect(self) -> None:
        """Initialize and connect to the MetaTrader 5 terminal."""

        if self._connected:
            return

        kwargs: dict[str, object] = {}

        if self.login is not None:
            kwargs["login"] = self.login

        if self.password is not None:
            kwargs["password"] = self.password

        if self.server is not None:
            kwargs["server"] = self.server

        if self.path is not None:
            kwargs["path"] = self.path

        if not mt5.initialize(**kwargs):
            error = mt5.last_error()
            raise RuntimeError(
                f"Failed to initialize MetaTrader 5: {error}"
            )

        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the MetaTrader 5 terminal."""

        if self._connected:
            mt5.shutdown()

        self._connected = False

    async def is_connected(self) -> bool:
        """Return the current connection state."""

        if not self._connected:
            return False

        terminal = mt5.terminal_info()

        if terminal is None:
            self._connected = False
            return False

        return True

    async def get_account_balance(self) -> float:
        """Return the current MT5 account balance."""

        self._require_connection()

        account = mt5.account_info()

        if account is None:
            raise RuntimeError(
                f"Unable to retrieve MT5 account information: "
                f"{mt5.last_error()}"
            )

        return float(account.balance)

    async def get_instrument(self, symbol: str) -> Instrument:
        """Return broker metadata for an MT5 instrument."""

        self._require_connection()

        info = mt5.symbol_info(symbol)

        if info is None:
            raise KeyError(f"Instrument not found: {symbol}")

        if not info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Unable to select MT5 instrument: {symbol}"
            )

        info = mt5.symbol_info(symbol)

        if info is None:
            raise KeyError(f"Instrument not found: {symbol}")

        tick_size = Decimal(str(info.trade_tick_size))
        contract_size = Decimal(str(info.trade_contract_size))
        min_volume = Decimal(str(info.volume_min))
        max_volume = Decimal(str(info.volume_max))
        volume_step = Decimal(str(info.volume_step))

        if tick_size <= Decimal(0):
            raise ValueError(f"Invalid tick size for {symbol}")

        if contract_size <= Decimal(0):
            raise ValueError(f"Invalid contract size for {symbol}")

        if min_volume <= Decimal(0):
            raise ValueError(f"Invalid minimum volume for {symbol}")

        if max_volume <= Decimal(0):
            raise ValueError(f"Invalid maximum volume for {symbol}")

        if volume_step <= Decimal(0):
            raise ValueError(f"Invalid volume step for {symbol}")

        return Instrument(
            symbol=symbol,
            name=info.name,
            asset_class=self._asset_class(info),
            quote_currency=str(
                getattr(info, "currency_profit", "") or ""
            ),
            broker_symbol=info.name,
            tick_size=tick_size,
            contract_size=contract_size,
            min_volume=min_volume,
            max_volume=max_volume,
            volume_step=volume_step,
            price_precision=info.digits,
            volume_precision=self._volume_precision(volume_step),
            enabled=bool(info.visible),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def submit_order(self, order: Order) -> Order:
        """Submit a market order to MetaTrader 5."""

        self._require_connection()

        if order.order_type is not OrderType.MARKET:
            raise ValueError(
                "MT5ExecutionProvider currently supports market orders only"
            )

        instrument = await self.get_instrument(order.symbol)

        if not instrument.enabled:
            raise RuntimeError(
                f"Instrument is not enabled: {order.symbol}"
            )

        if order.quantity < instrument.min_volume:
            raise ValueError(
                f"Order quantity {order.quantity} is below "
                f"minimum volume {instrument.min_volume}"
            )

        if (
            instrument.max_volume is not None
            and order.quantity > instrument.max_volume
        ):
            raise ValueError(
                f"Order quantity {order.quantity} exceeds "
                f"maximum volume {instrument.max_volume}"
            )

        if order.quantity % instrument.volume_step != 0:
            raise ValueError(
                f"Order quantity {order.quantity} must be aligned "
                f"with volume step {instrument.volume_step}"
            )

        tick = mt5.symbol_info_tick(order.symbol)

        if tick is None:
            raise RuntimeError(
                f"Unable to retrieve tick data: {order.symbol}"
            )

        if order.side is OrderSide.BUY:
            mt5_order_type = mt5.ORDER_TYPE_BUY
            price = Decimal(str(tick.ask))
        else:
            mt5_order_type = mt5.ORDER_TYPE_SELL
            price = Decimal(str(tick.bid))

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": float(order.quantity),
            "type": mt5_order_type,
            "price": float(price),
            "sl": (
                float(order.stop_loss)
                if order.stop_loss is not None
                else 0.0
            ),
            "tp": (
                float(order.take_profit)
                if order.take_profit is not None
                else 0.0
            ),
            "deviation": 20,
            "magic": 260815,
            "comment": "AtlasTrader",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError(
                f"MT5 order submission failed: {mt5.last_error()}"
            )

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(
                f"MT5 order rejected: "
                f"retcode={result.retcode}, "
                f"comment={result.comment}"
            )

        return order.model_copy(
            update={
                "status": OrderStatus.FILLED,
                "price": Decimal(str(result.price)),
                "updated_at": datetime.now(UTC),
            }
        )

    async def get_position(self, symbol: str) -> Position | None:
        """Return the current MT5 position for a symbol."""

        self._require_connection()

        positions = mt5.positions_get(symbol=symbol)

        if positions is None:
            raise RuntimeError(
                f"Unable to retrieve position: {mt5.last_error()}"
            )

        if not positions:
            return None

        position = positions[0]

        side = (
            OrderSide.BUY
            if position.type == mt5.POSITION_TYPE_BUY
            else OrderSide.SELL
        )

        return Position(
            symbol=position.symbol,
            side=side,
            status=PositionStatus.OPEN,
            quantity=Decimal(str(position.volume)),
            entry_price=Decimal(str(position.price_open)),
            current_price=Decimal(str(position.price_current)),
            stop_loss=(
                Decimal(str(position.sl))
                if position.sl
                else None
            ),
            take_profit=(
                Decimal(str(position.tp))
                if position.tp
                else None
            ),
            opened_at=datetime.fromtimestamp(
                position.time,
                tz=UTC,
            ),
            closed_at=None,
            realized_pnl=Decimal(0),
            unrealized_pnl=Decimal(str(position.profit)),
        )

    @staticmethod
    def _require_connection() -> None:
        """Raise when the MT5 terminal is not initialized."""

        if mt5.terminal_info() is None:
            raise RuntimeError(
                "MetaTrader 5 is not connected"
            )

    @staticmethod
    def _asset_class(info: object) -> AssetClass:
        """Infer AtlasTrader asset class from MT5 metadata."""

        name = str(getattr(info, "name", "")).upper()
        path = str(getattr(info, "path", "")).upper()

        combined = f"{name} {path}"

        if any(
            value in combined
            for value in ("XAU", "XAG", "GOLD", "SILVER")
        ):
            return AssetClass.METAL

        if any(
            value in combined
            for value in (
                "INDEX",
                "INDICES",
                "US30",
                "US500",
                "NAS100",
                "GER40",
                "UK100",
            )
        ):
            return AssetClass.INDEX

        if any(
            value in combined
            for value in (
                "OIL",
                "WTI",
                "BRENT",
                "GAS",
                "COMMODITY",
            )
        ):
            return AssetClass.COMMODITY

        if any(
            value in combined
            for value in (
                "BTC",
                "ETH",
                "CRYPTO",
            )
        ):
            return AssetClass.CRYPTO

        return AssetClass.FOREX

    @staticmethod
    def _volume_precision(step: Decimal) -> int:
        """Determine volume precision from the broker volume step."""

        exponent = step.as_tuple().exponent

        if not isinstance(exponent, int):
            return 0

        return max(0, -exponent)

    async def get_positions(self) -> list[Position]:
        """Return all current MT5 positions."""

        self._require_connection()

        positions = mt5.positions_get()

        if positions is None:
            raise RuntimeError(
                f"Unable to retrieve positions: {mt5.last_error()}"
            )

        result: list[Position] = []

        for position in positions:
            side = (
                OrderSide.BUY
                if position.type == mt5.POSITION_TYPE_BUY
                else OrderSide.SELL
            )

            result.append(
                Position(
                    symbol=position.symbol,
                    side=side,
                    status=PositionStatus.OPEN,
                    quantity=Decimal(str(position.volume)),
                    entry_price=Decimal(str(position.price_open)),
                    current_price=Decimal(
                        str(position.price_current)
                    ),
                    stop_loss=(
                        Decimal(str(position.sl))
                        if position.sl
                        else None
                    ),
                    take_profit=(
                        Decimal(str(position.tp))
                        if position.tp
                        else None
                    ),
                    opened_at=datetime.fromtimestamp(
                        position.time,
                        tz=UTC,
                    ),
                    closed_at=None,
                    realized_pnl=Decimal(0),
                    unrealized_pnl=Decimal(str(position.profit)),
                )
            )

        return result