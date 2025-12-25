"""Tests for execution service."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tlh_agent.brokers.alpaca import AlpacaClient, AlpacaOrder
from tlh_agent.data.local_store import HarvestQueueItem, LocalStore
from tlh_agent.services.execution import (
    ExecutionResult,
    ExecutionStatus,
    HarvestExecutionService,
)
from tlh_agent.services.wash_sale import WashSaleService


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalStore:
    """Create a temporary local store."""
    return LocalStore(tmp_path / "state.json")


@pytest.fixture
def wash_sale_service(temp_store: LocalStore) -> WashSaleService:
    """Create wash sale service."""
    return WashSaleService(temp_store)


def make_filled_order(
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
) -> AlpacaOrder:
    """Create a filled order."""
    return AlpacaOrder(
        id=f"order-{symbol}-{side}",
        symbol=symbol,
        side=side,
        qty=qty,
        filled_qty=qty,
        filled_avg_price=price,
        status="filled",
        submitted_at=datetime.now(),
        filled_at=datetime.now(),
    )


@pytest.fixture
def mock_alpaca() -> MagicMock:
    """Create mock Alpaca client."""
    mock = MagicMock(spec=AlpacaClient)
    return mock


@pytest.fixture
def execution_service(
    mock_alpaca: MagicMock,
    temp_store: LocalStore,
    wash_sale_service: WashSaleService,
) -> HarvestExecutionService:
    """Create execution service with mocks."""
    return HarvestExecutionService(mock_alpaca, temp_store, wash_sale_service)


def make_queue_item(
    ticker: str = "AAPL",
    shares: Decimal = Decimal("100"),
    cost_basis: Decimal = Decimal("15000"),
    store: LocalStore | None = None,
) -> HarvestQueueItem:
    """Create a harvest queue item."""
    item = HarvestQueueItem(
        id=store.new_id() if store else "test-id",
        ticker=ticker,
        shares=shares,
        current_price=Decimal("140"),
        cost_basis=cost_basis,
        unrealized_loss=Decimal("-1000"),
        estimated_tax_benefit=Decimal("350"),
        status="approved",
    )
    if store:
        store.add_harvest_item(item)
    return item


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_is_success_true(self) -> None:
        """Test is_success for successful result."""
        result = ExecutionResult(status=ExecutionStatus.SUCCESS)
        assert result.is_success is True

    def test_is_success_false_failed(self) -> None:
        """Test is_success for failed result."""
        result = ExecutionResult(status=ExecutionStatus.FAILED)
        assert result.is_success is False

    def test_is_success_false_pending(self) -> None:
        """Test is_success for pending result."""
        result = ExecutionResult(status=ExecutionStatus.PENDING)
        assert result.is_success is False


class TestHarvestExecutionService:
    """Tests for HarvestExecutionService."""

    def test_execute_harvest_success(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
    ) -> None:
        """Test successful harvest execution."""
        # Setup
        queue_item = make_queue_item(store=temp_store)
        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "sell", Decimal("100"), Decimal("140")
        )

        # Execute
        result = execution_service.execute_harvest(queue_item)

        # Verify
        assert result.is_success
        assert result.ticker == "AAPL"
        assert result.shares == Decimal("100")
        assert result.price == Decimal("140")
        assert result.total_value == Decimal("14000")
        # Realized loss: 14000 - 15000 = -1000
        assert result.realized_loss == Decimal("-1000")

    def test_execute_harvest_creates_restriction(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test harvest creates wash sale restriction."""
        queue_item = make_queue_item(store=temp_store)
        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "sell", Decimal("100"), Decimal("140")
        )

        execution_service.execute_harvest(queue_item)

        # Verify restriction created
        assert wash_sale_service.is_restricted("AAPL") is True
        restriction = wash_sale_service.get_restriction("AAPL")
        assert restriction.shares_sold == Decimal("100")

    def test_execute_harvest_updates_loss_ledger(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
    ) -> None:
        """Test harvest updates loss ledger."""
        queue_item = make_queue_item(store=temp_store)
        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "sell", Decimal("100"), Decimal("140")
        )

        execution_service.execute_harvest(queue_item)

        # Verify loss ledger updated
        ledger = temp_store.get_loss_ledger_year(date.today().year)
        assert ledger.short_term_losses == Decimal("1000")

    def test_execute_harvest_marks_queue_item_executed(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
    ) -> None:
        """Test harvest marks queue item as executed."""
        queue_item = make_queue_item(store=temp_store)
        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "sell", Decimal("100"), Decimal("140")
        )

        execution_service.execute_harvest(queue_item)

        # Verify queue item updated
        items = temp_store.get_harvest_queue()
        assert items[0].status == "executed"
        assert items[0].executed_at is not None

    def test_execute_harvest_pending_order(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
    ) -> None:
        """Test harvest with pending order."""
        queue_item = make_queue_item(store=temp_store)
        pending_order = AlpacaOrder(
            id="order-pending",
            symbol="AAPL",
            side="sell",
            qty=Decimal("100"),
            filled_qty=Decimal("0"),
            filled_avg_price=None,
            status="pending",
            submitted_at=datetime.now(),
            filled_at=None,
        )
        mock_alpaca.submit_market_order.return_value = pending_order

        result = execution_service.execute_harvest(queue_item)

        assert result.status == ExecutionStatus.PENDING
        assert result.order_id == "order-pending"

    def test_execute_harvest_failure(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        temp_store: LocalStore,
    ) -> None:
        """Test harvest execution failure."""
        queue_item = make_queue_item(store=temp_store)
        mock_alpaca.submit_market_order.side_effect = Exception("API error")

        result = execution_service.execute_harvest(queue_item)

        assert result.status == ExecutionStatus.FAILED
        assert "API error" in result.error_message

    def test_execute_rebuy_success(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test successful rebuy execution."""
        # Create an expired restriction
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("140"),
            sale_date=date.today() - timedelta(days=40),
        )

        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "buy", Decimal("100"), Decimal("145")
        )

        result = execution_service.execute_rebuy(restriction.id)

        assert result.is_success
        assert result.ticker == "AAPL"
        assert result.shares == Decimal("100")
        assert result.price == Decimal("145")

    def test_execute_rebuy_marks_restriction_complete(
        self,
        execution_service: HarvestExecutionService,
        mock_alpaca: MagicMock,
        wash_sale_service: WashSaleService,
        temp_store: LocalStore,
    ) -> None:
        """Test rebuy marks restriction as complete."""
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("140"),
            sale_date=date.today() - timedelta(days=40),
        )

        mock_alpaca.submit_market_order.return_value = make_filled_order(
            "AAPL", "buy", Decimal("100"), Decimal("145")
        )

        execution_service.execute_rebuy(restriction.id)

        # Verify restriction updated
        updated = temp_store.get_restrictions()[0]
        assert updated.rebuy_status == "completed"
        assert updated.rebuy_price == Decimal("145")

    def test_execute_rebuy_restriction_still_active(
        self,
        execution_service: HarvestExecutionService,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test rebuy fails if restriction still active."""
        # Create active restriction (not expired)
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("140"),
        )

        result = execution_service.execute_rebuy(restriction.id)

        assert result.status == ExecutionStatus.FAILED
        assert "still active" in result.error_message

    def test_execute_rebuy_restriction_not_found(
        self,
        execution_service: HarvestExecutionService,
    ) -> None:
        """Test rebuy with invalid restriction ID."""
        result = execution_service.execute_rebuy("invalid-id")

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.error_message

    def test_skip_rebuy(
        self,
        execution_service: HarvestExecutionService,
        wash_sale_service: WashSaleService,
        temp_store: LocalStore,
    ) -> None:
        """Test skipping rebuy."""
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("140"),
        )

        execution_service.skip_rebuy(restriction.id)

        updated = temp_store.get_restrictions()[0]
        assert updated.rebuy_status == "skipped"

    def test_get_pending_rebuys(
        self,
        execution_service: HarvestExecutionService,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test getting pending rebuys."""
        # Create expired restriction
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("140"),
            sale_date=date.today() - timedelta(days=40),
        )

        pending = execution_service.get_pending_rebuys()

        assert len(pending) == 1
        assert pending[0].ticker == "AAPL"

    def test_get_execution_summary(
        self,
        execution_service: HarvestExecutionService,
        temp_store: LocalStore,
    ) -> None:
        """Test getting execution summary."""
        # Add some loss to ledger
        from tlh_agent.data.local_store import LossLedgerYear
        ledger = LossLedgerYear(
            short_term_losses=Decimal("1500"),
            long_term_losses=Decimal("500"),
        )
        temp_store.update_loss_ledger_year(date.today().year, ledger)

        summary = execution_service.get_execution_summary()

        assert summary["year"] == date.today().year
        assert summary["total_harvested_losses"] == Decimal("2000")
        assert summary["short_term_losses"] == Decimal("1500")
        assert summary["long_term_losses"] == Decimal("500")
