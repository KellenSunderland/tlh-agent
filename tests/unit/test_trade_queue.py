"""Tests for trade queue service."""

from decimal import Decimal

import pytest

from tlh_agent.services.trade_queue import (
    QueuedTrade,
    TradeAction,
    TradeQueueService,
    TradeStatus,
    TradeType,
)


class TestTradeType:
    """Tests for TradeType enum."""

    def test_harvest_value(self) -> None:
        """Test harvest type value."""
        assert TradeType.HARVEST.value == "harvest"

    def test_index_buy_value(self) -> None:
        """Test index buy type value."""
        assert TradeType.INDEX_BUY.value == "index_buy"

    def test_rebalance_value(self) -> None:
        """Test rebalance type value."""
        assert TradeType.REBALANCE.value == "rebalance"


class TestTradeStatus:
    """Tests for TradeStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all status values exist."""
        assert TradeStatus.PENDING.value == "pending"
        assert TradeStatus.APPROVED.value == "approved"
        assert TradeStatus.REJECTED.value == "rejected"
        assert TradeStatus.EXECUTED.value == "executed"
        assert TradeStatus.FAILED.value == "failed"


class TestQueuedTrade:
    """Tests for QueuedTrade dataclass."""

    def test_create_harvest_trade(self) -> None:
        """Test creating a harvest trade."""
        trade = QueuedTrade(
            id="test-123",
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple Inc.",
            shares=Decimal("100"),
            notional=Decimal("15000"),
            current_price=Decimal("150"),
            status=TradeStatus.PENDING,
            reason="Tax-loss harvest",
            tax_impact=Decimal("-525"),
        )

        assert trade.id == "test-123"
        assert trade.trade_type == TradeType.HARVEST
        assert trade.action == TradeAction.SELL
        assert trade.symbol == "AAPL"
        assert trade.status == TradeStatus.PENDING

    def test_create_index_buy_trade(self) -> None:
        """Test creating an index buy trade."""
        trade = QueuedTrade(
            id="test-456",
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            notional=Decimal("4000"),
            current_price=Decimal("400"),
            status=TradeStatus.PENDING,
            reason="Track S&P 500",
        )

        assert trade.trade_type == TradeType.INDEX_BUY
        assert trade.action == TradeAction.BUY


class TestTradeQueueService:
    """Tests for TradeQueueService."""

    @pytest.fixture
    def service(self) -> TradeQueueService:
        """Create a TradeQueueService instance."""
        return TradeQueueService()

    def test_init_empty_queue(self, service: TradeQueueService) -> None:
        """Test service initializes with empty queue."""
        assert service.get_all_trades() == []

    def test_add_trade(self, service: TradeQueueService) -> None:
        """Test adding a trade to the queue."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple Inc.",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Tax-loss harvest",
            tax_impact=Decimal("-525"),
        )

        assert trade.id is not None
        assert trade.symbol == "AAPL"
        assert trade.status == TradeStatus.PENDING
        assert trade.notional == Decimal("15000.00")

        # Verify it's in the queue
        all_trades = service.get_all_trades()
        assert len(all_trades) == 1
        assert all_trades[0].id == trade.id

    def test_get_trade(self, service: TradeQueueService) -> None:
        """Test getting a trade by ID."""
        trade = service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Track index",
        )

        result = service.get_trade(trade.id)

        assert result is not None
        assert result.id == trade.id
        assert result.symbol == "MSFT"

    def test_get_trade_not_found(self, service: TradeQueueService) -> None:
        """Test getting a non-existent trade."""
        result = service.get_trade("not-a-real-id")

        assert result is None

    def test_get_trades_by_type(self, service: TradeQueueService) -> None:
        """Test filtering trades by type."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="GOOGL",
            name="Alphabet",
            shares=Decimal("50"),
            current_price=Decimal("140"),
            reason="Harvest",
        )

        harvest_trades = service.get_trades_by_type(TradeType.HARVEST)
        index_trades = service.get_trades_by_type(TradeType.INDEX_BUY)

        assert len(harvest_trades) == 2
        assert len(index_trades) == 1
        assert index_trades[0].symbol == "MSFT"

    def test_get_pending_trades(self, service: TradeQueueService) -> None:
        """Test getting pending trades."""
        trade1 = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        trade2 = service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )

        # Approve one trade
        service.approve_trade(trade1.id)

        pending = service.get_pending_trades()

        assert len(pending) == 1
        assert pending[0].id == trade2.id

    def test_approve_trade(self, service: TradeQueueService) -> None:
        """Test approving a trade."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )

        result = service.approve_trade(trade.id)

        assert result is True
        assert trade.status == TradeStatus.APPROVED

    def test_approve_trade_not_found(self, service: TradeQueueService) -> None:
        """Test approving non-existent trade."""
        result = service.approve_trade("not-a-real-id")

        assert result is False

    def test_approve_trade_not_pending(self, service: TradeQueueService) -> None:
        """Test approving already-approved trade."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.approve_trade(trade.id)

        # Try to approve again
        result = service.approve_trade(trade.id)

        assert result is False

    def test_reject_trade(self, service: TradeQueueService) -> None:
        """Test rejecting a trade."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )

        result = service.reject_trade(trade.id)

        assert result is True
        assert trade.status == TradeStatus.REJECTED

    def test_approve_all(self, service: TradeQueueService) -> None:
        """Test approving all pending trades."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )

        count = service.approve_all()

        assert count == 2
        assert len(service.get_pending_trades()) == 0
        assert len(service.get_trades_by_status(TradeStatus.APPROVED)) == 2

    def test_approve_all_by_type(self, service: TradeQueueService) -> None:
        """Test approving all pending trades of a specific type."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )

        count = service.approve_all(trade_type=TradeType.HARVEST)

        assert count == 1
        assert len(service.get_pending_trades()) == 1  # INDEX_BUY still pending

    def test_mark_executed(self, service: TradeQueueService) -> None:
        """Test marking a trade as executed."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.approve_trade(trade.id)

        result = service.mark_executed(trade.id, fill_price=Decimal("149.50"))

        assert result is True
        assert trade.status == TradeStatus.EXECUTED
        assert trade.fill_price == Decimal("149.50")
        assert trade.executed_at is not None

    def test_mark_executed_not_approved(self, service: TradeQueueService) -> None:
        """Test marking non-approved trade as executed."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )

        result = service.mark_executed(trade.id, fill_price=Decimal("149.50"))

        assert result is False
        assert trade.status == TradeStatus.PENDING

    def test_mark_failed(self, service: TradeQueueService) -> None:
        """Test marking a trade as failed."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )

        result = service.mark_failed(trade.id, error="Insufficient shares")

        assert result is True
        assert trade.status == TradeStatus.FAILED
        assert "Insufficient shares" in trade.reason

    def test_remove_trade(self, service: TradeQueueService) -> None:
        """Test removing a trade from the queue."""
        trade = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )

        result = service.remove_trade(trade.id)

        assert result is True
        assert service.get_trade(trade.id) is None

    def test_clear_queue(self, service: TradeQueueService) -> None:
        """Test clearing the queue."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )

        service.clear_queue()

        assert service.get_all_trades() == []

    def test_get_summary(self, service: TradeQueueService) -> None:
        """Test getting queue summary."""
        trade1 = service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )
        service.approve_trade(trade1.id)

        summary = service.get_summary()

        assert summary["pending"] == 1
        assert summary["approved"] == 1
        assert summary["rejected"] == 0
        assert summary["executed"] == 0
        assert summary["failed"] == 0

    def test_get_total_notional(self, service: TradeQueueService) -> None:
        """Test getting total notional value."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
        )
        service.add_trade(
            trade_type=TradeType.INDEX_BUY,
            action=TradeAction.BUY,
            symbol="MSFT",
            name="Microsoft",
            shares=Decimal("10"),
            current_price=Decimal("400"),
            reason="Index",
        )

        total = service.get_total_notional()

        assert total == Decimal("19000.00")

    def test_get_total_tax_impact(self, service: TradeQueueService) -> None:
        """Test getting total tax impact."""
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="AAPL",
            name="Apple",
            shares=Decimal("100"),
            current_price=Decimal("150"),
            reason="Harvest",
            tax_impact=Decimal("-350"),  # Savings
        )
        service.add_trade(
            trade_type=TradeType.HARVEST,
            action=TradeAction.SELL,
            symbol="GOOGL",
            name="Alphabet",
            shares=Decimal("50"),
            current_price=Decimal("140"),
            reason="Harvest",
            tax_impact=Decimal("-175"),  # Savings
        )

        total = service.get_total_tax_impact()

        assert total == Decimal("-525")
