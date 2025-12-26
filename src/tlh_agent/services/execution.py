"""Trade execution service for tax-loss harvesting."""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from tlh_agent.brokers.alpaca import AlpacaClient
from tlh_agent.data.local_store import HarvestQueueItem, LocalStore
from tlh_agent.services.trade_queue import QueuedTrade, TradeAction
from tlh_agent.services.wash_sale import WashSaleService

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of trade execution."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ExecutionResult:
    """Result of a trade execution."""

    status: ExecutionStatus
    order_id: str | None = None
    ticker: str = ""
    shares: Decimal = field(default_factory=lambda: Decimal("0"))
    price: Decimal = field(default_factory=lambda: Decimal("0"))
    total_value: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_loss: Decimal | None = None
    error_message: str | None = None
    executed_at: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        """Whether execution was successful."""
        return self.status == ExecutionStatus.SUCCESS


class HarvestExecutionService:
    """Executes tax-loss harvesting trades.

    Handles the full harvest workflow:
    1. Sell position to harvest loss
    2. Create wash sale restriction
    3. Update loss ledger
    4. Execute rebuy after restriction expires
    """

    def __init__(
        self,
        alpaca: AlpacaClient,
        store: LocalStore,
        wash_sale_service: WashSaleService | None = None,
    ) -> None:
        """Initialize execution service.

        Args:
            alpaca: Alpaca client for trade execution.
            store: Local store for persistence.
            wash_sale_service: Wash sale service (created if not provided).
        """
        self._alpaca = alpaca
        self._store = store
        self._wash_sale = wash_sale_service or WashSaleService(store)

    def execute_harvest(self, queue_item: HarvestQueueItem) -> ExecutionResult:
        """Execute a harvest sale.

        Sells all shares of the position and creates a wash sale restriction.

        Args:
            queue_item: The approved harvest queue item to execute.

        Returns:
            ExecutionResult with trade details.
        """
        try:
            # Submit market sell order
            order = self._alpaca.submit_market_order(
                symbol=queue_item.ticker,
                qty=queue_item.shares,
                side="sell",
            )

            if order.status != "filled":
                return ExecutionResult(
                    status=ExecutionStatus.PENDING,
                    order_id=order.id,
                    ticker=queue_item.ticker,
                    shares=queue_item.shares,
                )

            # Calculate realized loss
            sale_proceeds = order.filled_qty * (order.filled_avg_price or Decimal("0"))
            realized_loss = sale_proceeds - queue_item.cost_basis

            # Create wash sale restriction
            self._wash_sale.create_restriction(
                ticker=queue_item.ticker,
                shares_sold=order.filled_qty,
                sale_price=order.filled_avg_price or Decimal("0"),
            )

            # Update loss ledger
            self._update_loss_ledger(realized_loss)

            # Mark queue item as executed
            queue_item.status = "executed"
            queue_item.executed_at = datetime.now()
            self._store.update_harvest_item(queue_item)

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                order_id=order.id,
                ticker=queue_item.ticker,
                shares=order.filled_qty,
                price=order.filled_avg_price or Decimal("0"),
                total_value=sale_proceeds,
                realized_loss=realized_loss,
            )

        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                ticker=queue_item.ticker,
                shares=queue_item.shares,
                error_message=str(e),
            )

    def execute_rebuy(self, restriction_id: str) -> ExecutionResult:
        """Execute a rebuy after wash sale period expires.

        Args:
            restriction_id: ID of the wash sale restriction.

        Returns:
            ExecutionResult with trade details.
        """
        # Get restriction details
        restrictions = self._store.get_restrictions()
        restriction = None
        for r in restrictions:
            if r.id == restriction_id:
                restriction = r
                break

        if restriction is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_message=f"Restriction not found: {restriction_id}",
            )

        # Verify restriction has expired
        if restriction.is_active:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                ticker=restriction.ticker,
                error_message="Wash sale restriction still active",
            )

        try:
            # Submit market buy order
            order = self._alpaca.submit_market_order(
                symbol=restriction.ticker,
                qty=restriction.shares_sold,
                side="buy",
            )

            if order.status != "filled":
                return ExecutionResult(
                    status=ExecutionStatus.PENDING,
                    order_id=order.id,
                    ticker=restriction.ticker,
                    shares=restriction.shares_sold,
                )

            # Mark restriction as complete
            self._wash_sale.mark_rebuy_complete(
                restriction_id=restriction.id,
                rebuy_price=order.filled_avg_price or Decimal("0"),
            )

            total_value = order.filled_qty * (order.filled_avg_price or Decimal("0"))

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                order_id=order.id,
                ticker=restriction.ticker,
                shares=order.filled_qty,
                price=order.filled_avg_price or Decimal("0"),
                total_value=total_value,
            )

        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                ticker=restriction.ticker,
                error_message=str(e),
            )

    def skip_rebuy(self, restriction_id: str) -> None:
        """Skip rebuy for a restriction.

        Used when user decides not to repurchase the security.

        Args:
            restriction_id: ID of the wash sale restriction.
        """
        self._wash_sale.mark_rebuy_skipped(restriction_id)

    def execute_queued_trade(self, trade: QueuedTrade) -> ExecutionResult:
        """Execute a queued trade (buy or sell).

        Handles trades from the trade queue service (index buys, rebalances, etc.)

        Args:
            trade: The approved trade to execute.

        Returns:
            ExecutionResult with trade details.
        """
        side = "buy" if trade.action == TradeAction.BUY else "sell"
        logger.info(
            f"EXECUTE: {side.upper()} {trade.shares} {trade.symbol} @ ~${trade.current_price}"
        )

        try:
            # Submit market order based on action
            order = self._alpaca.submit_market_order(
                symbol=trade.symbol,
                qty=trade.shares,
                side=side,
            )

            # Check if order was filled immediately
            if order.status != "filled":
                logger.warning(f"  -> PENDING: order {order.id} status={order.status}")
                return ExecutionResult(
                    status=ExecutionStatus.PENDING,
                    order_id=order.id,
                    ticker=trade.symbol,
                    shares=trade.shares,
                )

            # Calculate total value
            fill_price = order.filled_avg_price or Decimal("0")
            total_value = order.filled_qty * fill_price

            logger.info(
                f"  -> SUCCESS: filled {order.filled_qty} @ ${fill_price} = ${total_value:.2f}"
            )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                order_id=order.id,
                ticker=trade.symbol,
                shares=order.filled_qty,
                price=fill_price,
                total_value=total_value,
            )

        except Exception as e:
            logger.error(f"  -> FAILED: {e}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                ticker=trade.symbol,
                shares=trade.shares,
                error_message=str(e),
            )

    def get_pending_rebuys(self) -> list:
        """Get restrictions ready for rebuy.

        Returns:
            List of expired restrictions with pending rebuy status.
        """
        return self._wash_sale.get_pending_rebuys()

    def _update_loss_ledger(self, realized_loss: Decimal) -> None:
        """Update loss ledger with realized loss.

        Args:
            realized_loss: The loss amount (negative = loss, positive = gain).
        """
        current_year = date.today().year
        ledger = self._store.get_loss_ledger_year(current_year)

        # Only update if this is actually a loss
        if realized_loss < 0:
            # For simplicity, treat all as short-term
            # In reality, this would depend on holding period
            ledger.short_term_losses += abs(realized_loss)

        self._store.update_loss_ledger_year(current_year, ledger)

    def get_execution_summary(self, year: int | None = None) -> dict:
        """Get summary of executions for a year.

        Args:
            year: The year to summarize (defaults to current year).

        Returns:
            Dict with execution statistics.
        """
        if year is None:
            year = date.today().year

        ledger = self._store.get_loss_ledger_year(year)
        restrictions = self._store.get_restrictions()

        # Count completed harvests
        completed = sum(
            1 for r in restrictions if r.rebuy_status == "completed" and r.sale_date.year == year
        )

        # Count pending rebuys
        pending = sum(1 for r in restrictions if r.rebuy_status == "pending" and not r.is_active)

        return {
            "year": year,
            "total_harvested_losses": ledger.total_losses,
            "short_term_losses": ledger.short_term_losses,
            "long_term_losses": ledger.long_term_losses,
            "completed_harvests": completed,
            "pending_rebuys": pending,
        }
