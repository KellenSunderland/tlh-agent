"""Trade queue service for managing pending trades.

Manages a unified queue of pending trades from multiple sources:
- Harvest opportunities (from scanner)
- Index buys (from Claude/index service)
- Rebalance trades (from rebalance service)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class TradeType(Enum):
    """Type of trade in the queue."""

    HARVEST = "harvest"  # Tax-loss harvesting sell
    INDEX_BUY = "index_buy"  # S&P 500 tracking buy
    REBALANCE = "rebalance"  # Drift correction trade


class TradeStatus(Enum):
    """Status of a trade in the queue."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class TradeAction(Enum):
    """Trade action type."""

    BUY = "buy"
    SELL = "sell"


@dataclass
class QueuedTrade:
    """A trade in the queue."""

    id: str
    trade_type: TradeType
    action: TradeAction
    symbol: str
    name: str
    shares: Decimal
    notional: Decimal  # Dollar value
    current_price: Decimal
    status: TradeStatus
    reason: str
    tax_impact: Decimal | None = None  # Tax savings (negative) or owed (positive)
    swap_target: str | None = None  # For harvest swaps
    wash_sale_blocked: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: datetime | None = None
    fill_price: Decimal | None = None
    source_id: str | None = None  # ID from source (e.g., harvest opportunity ID)


class TradeQueueService:
    """Service for managing the trade queue.

    Provides a unified view of pending trades from all sources.
    Trades are added by various services (scanner, Claude, rebalancer)
    and approved/executed by the user through the UI.
    """

    def __init__(self) -> None:
        """Initialize the trade queue service."""
        self._queue: dict[str, QueuedTrade] = {}

    def add_trade(
        self,
        trade_type: TradeType,
        action: TradeAction,
        symbol: str,
        name: str,
        shares: Decimal,
        current_price: Decimal,
        reason: str,
        tax_impact: Decimal | None = None,
        swap_target: str | None = None,
        wash_sale_blocked: bool = False,
        source_id: str | None = None,
    ) -> QueuedTrade:
        """Add a trade to the queue.

        Args:
            trade_type: Type of trade (harvest, index_buy, rebalance).
            action: Buy or sell.
            symbol: Stock symbol.
            name: Company name.
            shares: Number of shares.
            current_price: Current share price.
            reason: Reason for the trade.
            tax_impact: Expected tax impact.
            swap_target: Target symbol for swap (harvest only).
            wash_sale_blocked: Whether trade is blocked by wash sale.
            source_id: ID from the source service.

        Returns:
            The created QueuedTrade.
        """
        trade = QueuedTrade(
            id=str(uuid4()),
            trade_type=trade_type,
            action=action,
            symbol=symbol,
            name=name,
            shares=shares,
            notional=(shares * current_price).quantize(Decimal("0.01")),
            current_price=current_price,
            status=TradeStatus.PENDING,
            reason=reason,
            tax_impact=tax_impact,
            swap_target=swap_target,
            wash_sale_blocked=wash_sale_blocked,
            source_id=source_id,
        )

        self._queue[trade.id] = trade
        logger.info(
            "Added trade: %s %s %s x%.3f shares",
            trade_type.value, action.value, symbol, shares,
        )
        return trade

    def get_all_trades(self) -> list[QueuedTrade]:
        """Get all trades in the queue.

        Returns:
            List of all queued trades, sorted by creation time.
        """
        return sorted(self._queue.values(), key=lambda t: t.created_at, reverse=True)

    def get_trades_by_type(self, trade_type: TradeType) -> list[QueuedTrade]:
        """Get trades of a specific type.

        Args:
            trade_type: Type of trades to filter by.

        Returns:
            List of trades matching the type.
        """
        return [t for t in self.get_all_trades() if t.trade_type == trade_type]

    def get_trades_by_status(self, status: TradeStatus) -> list[QueuedTrade]:
        """Get trades with a specific status.

        Args:
            status: Status to filter by.

        Returns:
            List of trades matching the status.
        """
        return [t for t in self.get_all_trades() if t.status == status]

    def get_pending_trades(self) -> list[QueuedTrade]:
        """Get all pending trades.

        Returns:
            List of pending trades.
        """
        return self.get_trades_by_status(TradeStatus.PENDING)

    def get_trade(self, trade_id: str) -> QueuedTrade | None:
        """Get a trade by ID.

        Args:
            trade_id: The trade ID.

        Returns:
            The trade if found, None otherwise.
        """
        return self._queue.get(trade_id)

    def approve_trade(self, trade_id: str) -> bool:
        """Approve a trade.

        Args:
            trade_id: The trade ID to approve.

        Returns:
            True if approved, False if not found or not pending.
        """
        trade = self._queue.get(trade_id)
        if trade and trade.status == TradeStatus.PENDING:
            trade.status = TradeStatus.APPROVED
            logger.info("Approved trade %s (%s)", trade_id, trade.symbol)
            return True
        return False

    def reject_trade(self, trade_id: str) -> bool:
        """Reject a trade.

        Args:
            trade_id: The trade ID to reject.

        Returns:
            True if rejected, False if not found or not pending.
        """
        trade = self._queue.get(trade_id)
        if trade and trade.status == TradeStatus.PENDING:
            trade.status = TradeStatus.REJECTED
            logger.info("Rejected trade %s (%s)", trade_id, trade.symbol)
            return True
        return False

    def approve_all(self, trade_type: TradeType | None = None) -> int:
        """Approve all pending trades.

        Args:
            trade_type: Optional type filter.

        Returns:
            Number of trades approved.
        """
        count = 0
        for trade in self.get_pending_trades():
            if trade_type is None or trade.trade_type == trade_type:
                trade.status = TradeStatus.APPROVED
                count += 1
        logger.info("Approved all: %d trades", count)
        return count

    def reject_all(self, trade_type: TradeType | None = None) -> int:
        """Reject all pending trades.

        Args:
            trade_type: Optional type filter.

        Returns:
            Number of trades rejected.
        """
        count = 0
        for trade in self.get_pending_trades():
            if trade_type is None or trade.trade_type == trade_type:
                trade.status = TradeStatus.REJECTED
                count += 1
        return count

    def mark_executed(
        self,
        trade_id: str,
        fill_price: Decimal,
    ) -> bool:
        """Mark a trade as executed.

        Args:
            trade_id: The trade ID.
            fill_price: The execution price.

        Returns:
            True if marked, False if not found or not approved.
        """
        trade = self._queue.get(trade_id)
        if trade and trade.status == TradeStatus.APPROVED:
            trade.status = TradeStatus.EXECUTED
            trade.executed_at = datetime.now()
            trade.fill_price = fill_price
            logger.info("Executed trade %s (%s) at $%.2f", trade_id, trade.symbol, fill_price)
            return True
        return False

    def mark_failed(self, trade_id: str, error: str | None = None) -> bool:
        """Mark a trade as failed.

        Args:
            trade_id: The trade ID.
            error: Optional error message.

        Returns:
            True if marked, False if not found.
        """
        trade = self._queue.get(trade_id)
        if trade:
            trade.status = TradeStatus.FAILED
            if error:
                trade.reason = f"{trade.reason} - Failed: {error}"
            logger.info("Failed trade %s (%s): %s", trade_id, trade.symbol, error or "unknown")
            return True
        return False

    def remove_trade(self, trade_id: str) -> bool:
        """Remove a trade from the queue.

        Args:
            trade_id: The trade ID to remove.

        Returns:
            True if removed, False if not found.
        """
        if trade_id in self._queue:
            del self._queue[trade_id]
            return True
        return False

    def clear_queue(self) -> None:
        """Clear all trades from the queue."""
        count = len(self._queue)
        self._queue.clear()
        logger.info("Cleared queue: %d trades removed", count)

    def get_summary(self) -> dict[str, int]:
        """Get summary counts by status.

        Returns:
            Dictionary with counts by status.
        """
        summary = {status.value: 0 for status in TradeStatus}
        for trade in self._queue.values():
            summary[trade.status.value] += 1
        logger.debug("Queue summary: %s", summary)
        return summary

    def get_total_notional(self, status: TradeStatus | None = None) -> Decimal:
        """Get total notional value of trades.

        Args:
            status: Optional status filter.

        Returns:
            Total notional value.
        """
        trades = self.get_trades_by_status(status) if status else self.get_all_trades()
        return sum((t.notional for t in trades), Decimal("0"))

    def get_total_tax_impact(self, status: TradeStatus | None = None) -> Decimal:
        """Get total tax impact of trades.

        Args:
            status: Optional status filter.

        Returns:
            Total tax impact (negative = savings).
        """
        trades = self.get_trades_by_status(status) if status else self.get_all_trades()
        return sum((t.tax_impact for t in trades if t.tax_impact), Decimal("0"))
