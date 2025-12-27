"""Portfolio service for TLH Agent.

Wraps the Alpaca client and provides data in a format compatible
with the UI layer, replacing the mock data factory.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tlh_agent.brokers.alpaca import AlpacaClient, AlpacaOrder, AlpacaPosition
from tlh_agent.data.local_store import LocalStore
from tlh_agent.services.wash_sale import WashSaleService


@dataclass
class PortfolioSummary:
    """Summary metrics for the portfolio."""

    total_value: Decimal
    total_cost_basis: Decimal
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_pct: Decimal
    ytd_harvested_losses: Decimal
    pending_harvest_opportunities: int
    active_wash_sale_restrictions: int


@dataclass
class Position:
    """A portfolio position."""

    ticker: str
    name: str
    shares: Decimal
    avg_cost_per_share: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_pct: Decimal
    wash_sale_until: date | None = None

    @classmethod
    def from_alpaca(
        cls,
        alpaca_pos: AlpacaPosition,
        wash_sale_until: date | None = None,
    ) -> "Position":
        """Create from Alpaca position data.

        Args:
            alpaca_pos: Position from Alpaca API.
            wash_sale_until: Date when wash sale restriction ends, if any.

        Returns:
            Position instance.
        """
        gain_loss_pct = Decimal("0")
        if alpaca_pos.cost_basis > 0:
            gain_loss_pct = (alpaca_pos.unrealized_pl / alpaca_pos.cost_basis) * 100

        return cls(
            ticker=alpaca_pos.symbol,
            name=alpaca_pos.symbol,  # Alpaca doesn't provide company name
            shares=alpaca_pos.qty,
            avg_cost_per_share=alpaca_pos.avg_entry_price,
            current_price=alpaca_pos.current_price,
            market_value=alpaca_pos.market_value,
            cost_basis=alpaca_pos.cost_basis,
            unrealized_gain_loss=alpaca_pos.unrealized_pl,
            unrealized_gain_loss_pct=gain_loss_pct.quantize(Decimal("0.01")),
            wash_sale_until=wash_sale_until,
        )


@dataclass
class Trade:
    """A trade execution record."""

    id: str
    ticker: str
    trade_type: str  # "buy" or "sell"
    shares: Decimal
    price_per_share: Decimal
    executed_at: date
    total_value: Decimal
    harvest_event_id: str | None = None

    @classmethod
    def from_alpaca(
        cls,
        alpaca_order: AlpacaOrder,
        harvest_event_id: str | None = None,
    ) -> "Trade":
        """Create from Alpaca order data.

        Args:
            alpaca_order: Filled order from Alpaca API.
            harvest_event_id: Optional harvest event ID if this was a TLH trade.

        Returns:
            Trade instance.
        """
        price = alpaca_order.filled_avg_price or Decimal("0")
        return cls(
            id=alpaca_order.id,
            ticker=alpaca_order.symbol,
            trade_type=alpaca_order.side,
            shares=alpaca_order.filled_qty,
            price_per_share=price,
            executed_at=alpaca_order.filled_at.date() if alpaca_order.filled_at else date.today(),
            total_value=alpaca_order.filled_qty * price,
            harvest_event_id=harvest_event_id,
        )


@dataclass
class TradeFilters:
    """Filters for trade history queries."""

    ticker: str | None = None
    trade_type: str | None = None  # "buy" or "sell"
    start_date: date | None = None
    end_date: date | None = None
    harvest_only: bool = False


class PortfolioService:
    """Service for portfolio data and operations.

    Wraps the Alpaca client to provide portfolio data in a
    UI-compatible format. Uses LocalStore for wash sale tracking.
    """

    def __init__(
        self,
        alpaca: AlpacaClient,
        store: LocalStore,
        wash_sale_service: WashSaleService | None = None,
    ) -> None:
        """Initialize portfolio service.

        Args:
            alpaca: Alpaca client for market data.
            store: Local store for TLH state.
            wash_sale_service: Wash sale service (created if not provided).
        """
        self._alpaca = alpaca
        self._store = store
        self._wash_sale = wash_sale_service or WashSaleService(store)

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary metrics.

        Returns:
            Summary with totals and counts.
        """
        # Get account equity (this accounts for margin/cash correctly)
        account = self._alpaca.get_account()
        total_value = account.equity

        # Get positions for cost basis and unrealized P/L
        positions = self._alpaca.get_positions()
        total_cost = sum((p.cost_basis for p in positions), Decimal("0"))
        unrealized_pl = sum((p.unrealized_pl for p in positions), Decimal("0"))

        # Calculate percentage
        unrealized_pct = Decimal("0")
        if total_cost > 0:
            unrealized_pct = (unrealized_pl / total_cost) * 100

        # Get YTD harvested losses from loss ledger
        current_year = date.today().year
        loss_ledger = self._store.get_loss_ledger_year(current_year)
        ytd_losses = loss_ledger.total_losses

        # Get counts
        pending_harvests = len(self._store.get_pending_harvests())
        active_restrictions = len(self._wash_sale.get_active_restrictions())

        return PortfolioSummary(
            total_value=total_value,
            total_cost_basis=total_cost,
            unrealized_gain_loss=unrealized_pl,
            unrealized_gain_loss_pct=unrealized_pct.quantize(Decimal("0.01")),
            ytd_harvested_losses=-ytd_losses,  # Show as negative
            pending_harvest_opportunities=pending_harvests,
            active_wash_sale_restrictions=active_restrictions,
        )

    def get_positions(self) -> list[Position]:
        """Get all portfolio positions.

        Returns:
            List of positions with wash sale info.
        """
        alpaca_positions = self._alpaca.get_positions()
        positions = []

        for ap in alpaca_positions:
            # Check for wash sale restriction
            wash_until = self._wash_sale.get_clear_date(ap.symbol)
            position = Position.from_alpaca(ap, wash_sale_until=wash_until)
            positions.append(position)

        # Sort by market value descending
        positions.sort(key=lambda p: p.market_value, reverse=True)
        return positions

    def get_position(self, ticker: str) -> Position | None:
        """Get a specific position by ticker.

        Args:
            ticker: The stock symbol.

        Returns:
            Position if found, None otherwise.
        """
        positions = self.get_positions()
        for p in positions:
            if p.ticker == ticker:
                return p
        return None

    def get_trade_history(
        self,
        filters: TradeFilters | None = None,
        days: int = 365,
    ) -> list[Trade]:
        """Get trade history from Alpaca.

        Args:
            filters: Optional filters to apply.
            days: Number of days of history to fetch.

        Returns:
            List of trades matching filters.
        """
        alpaca_orders = self._alpaca.get_order_history(days=days)

        # Convert to Trade objects
        trades = [Trade.from_alpaca(o) for o in alpaca_orders]

        # Apply filters
        if filters:
            if filters.ticker:
                trades = [t for t in trades if t.ticker == filters.ticker]
            if filters.trade_type:
                trades = [t for t in trades if t.trade_type == filters.trade_type]
            if filters.start_date:
                trades = [t for t in trades if t.executed_at >= filters.start_date]
            if filters.end_date:
                trades = [t for t in trades if t.executed_at <= filters.end_date]
            # Note: harvest_only filter would need harvest event tracking

        # Sort by date descending
        trades.sort(key=lambda t: t.executed_at, reverse=True)
        return trades

    def get_alpaca_positions(self) -> list[AlpacaPosition]:
        """Get raw Alpaca positions.

        Useful for the scanner which needs AlpacaPosition objects.

        Returns:
            List of Alpaca positions.
        """
        return self._alpaca.get_positions()

    def get_alpaca_orders(self, days: int = 365) -> list[AlpacaOrder]:
        """Get raw Alpaca order history.

        Useful for the scanner which needs AlpacaOrder objects.

        Args:
            days: Number of days of history.

        Returns:
            List of Alpaca orders.
        """
        return self._alpaca.get_order_history(days=days)

    def get_total_value(self) -> Decimal:
        """Get total portfolio value (account equity).

        Returns:
            Account equity (positions minus margin debt).
        """
        account = self._alpaca.get_account()
        return account.equity
