"""Alpaca broker client for TLH Agent."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest


@dataclass
class AlpacaPosition:
    """Position data from Alpaca."""

    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal


@dataclass
class AlpacaOrder:
    """Order data from Alpaca."""

    id: str
    symbol: str
    side: str  # "buy" or "sell"
    qty: Decimal
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    status: str
    submitted_at: datetime
    filled_at: datetime | None


@dataclass
class AlpacaAccount:
    """Account data from Alpaca."""

    id: str
    status: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal


class AlpacaClient:
    """Client for Alpaca Trading API."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
    ) -> None:
        """Initialize Alpaca client.

        Args:
            api_key: Alpaca API key.
            secret_key: Alpaca secret key.
            paper: Whether to use paper trading (default True).
        """
        self._client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )
        self._paper = paper

    @property
    def is_paper(self) -> bool:
        """Whether this is a paper trading account."""
        return self._paper

    def get_account(self) -> AlpacaAccount:
        """Get account information."""
        account = self._client.get_account()
        return AlpacaAccount(
            id=str(account.id),
            status=account.status.value if account.status else "unknown",
            equity=Decimal(str(account.equity or "0")),
            cash=Decimal(str(account.cash or "0")),
            buying_power=Decimal(str(account.buying_power or "0")),
        )

    def get_positions(self) -> list[AlpacaPosition]:
        """Get all open positions."""
        positions = self._client.get_all_positions()
        return [
            AlpacaPosition(
                symbol=p.symbol,
                qty=Decimal(str(p.qty)),
                avg_entry_price=Decimal(str(p.avg_entry_price)),
                current_price=Decimal(str(p.current_price or "0")),
                market_value=Decimal(str(p.market_value or "0")),
                cost_basis=Decimal(str(p.cost_basis)),
                unrealized_pl=Decimal(str(p.unrealized_pl or "0")),
                unrealized_plpc=Decimal(str(p.unrealized_plpc or "0")),
            )
            for p in positions
        ]

    def get_order_history(self, days: int = 365) -> list[AlpacaOrder]:
        """Get order history for the specified number of days.

        Args:
            days: Number of days of history to retrieve.

        Returns:
            List of orders sorted by date descending.
        """
        after = datetime.now() - timedelta(days=days)
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=after,
        )
        orders = self._client.get_orders(request)
        return [self._convert_order(o) for o in orders]

    def get_filled_orders(self, days: int = 365) -> list[AlpacaOrder]:
        """Get only filled orders.

        Args:
            days: Number of days of history to retrieve.

        Returns:
            List of filled orders sorted by date descending.
        """
        after = datetime.now() - timedelta(days=days)
        request = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=after,
        )
        orders = self._client.get_orders(request)
        # Filter to only filled orders (CLOSED includes cancelled too)
        return [
            self._convert_order(o)
            for o in orders
            if o.status == OrderStatus.FILLED
        ]

    def get_order(self, order_id: str) -> AlpacaOrder:
        """Get a specific order by ID.

        Args:
            order_id: The order ID.

        Returns:
            The order.
        """
        order = self._client.get_order_by_id(order_id)
        return self._convert_order(order)

    def submit_market_order(
        self,
        symbol: str,
        qty: Decimal,
        side: str,
    ) -> AlpacaOrder:
        """Submit a market order.

        Args:
            symbol: Stock symbol.
            qty: Number of shares.
            side: "buy" or "sell".

        Returns:
            The submitted order.
        """
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        request = MarketOrderRequest(
            symbol=symbol,
            qty=float(qty),
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(request)
        return self._convert_order(order)

    def submit_limit_order(
        self,
        symbol: str,
        qty: Decimal,
        side: str,
        limit_price: Decimal,
    ) -> AlpacaOrder:
        """Submit a limit order.

        Args:
            symbol: Stock symbol.
            qty: Number of shares.
            side: "buy" or "sell".
            limit_price: Limit price.

        Returns:
            The submitted order.
        """
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        request = LimitOrderRequest(
            symbol=symbol,
            qty=float(qty),
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=float(limit_price),
        )
        order = self._client.submit_order(request)
        return self._convert_order(order)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: The order ID to cancel.

        Returns:
            True if cancelled successfully.
        """
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def _convert_order(self, order) -> AlpacaOrder:
        """Convert Alpaca SDK order to our dataclass."""
        return AlpacaOrder(
            id=str(order.id),
            symbol=order.symbol or "",
            side=order.side.value if order.side else "unknown",
            qty=Decimal(str(order.qty or 0)),
            filled_qty=Decimal(str(order.filled_qty or 0)),
            filled_avg_price=(
                Decimal(str(order.filled_avg_price))
                if order.filled_avg_price
                else None
            ),
            status=order.status.value if order.status else "unknown",
            submitted_at=order.submitted_at or datetime.now(),
            filled_at=order.filled_at,
        )
