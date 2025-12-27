"""Tests for portfolio service."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tlh_agent.brokers.alpaca import (
    AlpacaAccount,
    AlpacaClient,
    AlpacaOrder,
    AlpacaPosition,
)
from tlh_agent.data.local_store import LocalStore
from tlh_agent.services.portfolio import (
    PortfolioService,
    PortfolioSummary,
    Position,
    Trade,
    TradeFilters,
)
from tlh_agent.services.wash_sale import WashSaleService


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalStore:
    """Create a temporary local store."""
    return LocalStore(tmp_path / "state.json")


@pytest.fixture
def mock_alpaca() -> MagicMock:
    """Create a mock Alpaca client."""
    mock = MagicMock(spec=AlpacaClient)

    # Mock account
    # equity should match sum of positions for test consistency
    mock.get_account.return_value = AlpacaAccount(
        id="test-account",
        status="ACTIVE",
        equity=Decimal("22000.00"),  # 15500 + 6500 = sum of positions
        cash=Decimal("10000.00"),
        buying_power=Decimal("20000.00"),
    )

    # Mock positions
    mock.get_positions.return_value = [
        AlpacaPosition(
            symbol="AAPL",
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("155.00"),
            market_value=Decimal("15500.00"),
            cost_basis=Decimal("15000.00"),
            unrealized_pl=Decimal("500.00"),
            unrealized_plpc=Decimal("0.0333"),
        ),
        AlpacaPosition(
            symbol="GOOGL",
            qty=Decimal("50"),
            avg_entry_price=Decimal("140.00"),
            current_price=Decimal("130.00"),
            market_value=Decimal("6500.00"),
            cost_basis=Decimal("7000.00"),
            unrealized_pl=Decimal("-500.00"),
            unrealized_plpc=Decimal("-0.0714"),
        ),
    ]

    # Mock order history
    mock.get_order_history.return_value = [
        AlpacaOrder(
            id="order-1",
            symbol="AAPL",
            side="buy",
            qty=Decimal("100"),
            filled_qty=Decimal("100"),
            filled_avg_price=Decimal("150.00"),
            status="filled",
            submitted_at=datetime.now() - timedelta(days=30),
            filled_at=datetime.now() - timedelta(days=30),
        ),
        AlpacaOrder(
            id="order-2",
            symbol="GOOGL",
            side="buy",
            qty=Decimal("50"),
            filled_qty=Decimal("50"),
            filled_avg_price=Decimal("140.00"),
            status="filled",
            submitted_at=datetime.now() - timedelta(days=20),
            filled_at=datetime.now() - timedelta(days=20),
        ),
    ]

    return mock


@pytest.fixture
def wash_sale_service(temp_store: LocalStore) -> WashSaleService:
    """Create wash sale service."""
    return WashSaleService(temp_store)


@pytest.fixture
def portfolio_service(
    mock_alpaca: MagicMock,
    temp_store: LocalStore,
    wash_sale_service: WashSaleService,
) -> PortfolioService:
    """Create portfolio service with mocks."""
    return PortfolioService(mock_alpaca, temp_store, wash_sale_service)


class TestPosition:
    """Tests for Position dataclass."""

    def test_from_alpaca(self) -> None:
        """Test creating Position from Alpaca data."""
        alpaca_pos = AlpacaPosition(
            symbol="AAPL",
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("160.00"),
            market_value=Decimal("16000.00"),
            cost_basis=Decimal("15000.00"),
            unrealized_pl=Decimal("1000.00"),
            unrealized_plpc=Decimal("0.0667"),
        )

        position = Position.from_alpaca(alpaca_pos)

        assert position.ticker == "AAPL"
        assert position.shares == Decimal("100")
        assert position.avg_cost_per_share == Decimal("150.00")
        assert position.current_price == Decimal("160.00")
        assert position.market_value == Decimal("16000.00")
        assert position.unrealized_gain_loss == Decimal("1000.00")
        assert position.wash_sale_until is None

    def test_from_alpaca_with_wash_sale(self) -> None:
        """Test creating Position with wash sale restriction."""
        alpaca_pos = AlpacaPosition(
            symbol="AAPL",
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("160.00"),
            market_value=Decimal("16000.00"),
            cost_basis=Decimal("15000.00"),
            unrealized_pl=Decimal("1000.00"),
            unrealized_plpc=Decimal("0.0667"),
        )
        wash_until = date.today() + timedelta(days=15)

        position = Position.from_alpaca(alpaca_pos, wash_sale_until=wash_until)

        assert position.wash_sale_until == wash_until


class TestTrade:
    """Tests for Trade dataclass."""

    def test_from_alpaca(self) -> None:
        """Test creating Trade from Alpaca order."""
        filled_at = datetime.now() - timedelta(days=5)
        alpaca_order = AlpacaOrder(
            id="order-123",
            symbol="AAPL",
            side="buy",
            qty=Decimal("100"),
            filled_qty=Decimal("100"),
            filled_avg_price=Decimal("150.00"),
            status="filled",
            submitted_at=filled_at - timedelta(minutes=1),
            filled_at=filled_at,
        )

        trade = Trade.from_alpaca(alpaca_order)

        assert trade.id == "order-123"
        assert trade.ticker == "AAPL"
        assert trade.trade_type == "buy"
        assert trade.shares == Decimal("100")
        assert trade.price_per_share == Decimal("150.00")
        assert trade.total_value == Decimal("15000.00")
        assert trade.executed_at == filled_at.date()


class TestPortfolioService:
    """Tests for PortfolioService."""

    def test_get_portfolio_summary(self, portfolio_service: PortfolioService) -> None:
        """Test getting portfolio summary."""
        summary = portfolio_service.get_portfolio_summary()

        assert isinstance(summary, PortfolioSummary)
        assert summary.total_value == Decimal("22000.00")  # 15500 + 6500
        assert summary.total_cost_basis == Decimal("22000.00")  # 15000 + 7000
        assert summary.unrealized_gain_loss == Decimal("0.00")  # 500 - 500
        assert summary.pending_harvest_opportunities == 0
        assert summary.active_wash_sale_restrictions == 0

    def test_get_positions(self, portfolio_service: PortfolioService) -> None:
        """Test getting positions."""
        positions = portfolio_service.get_positions()

        assert len(positions) == 2
        # Sorted by market value descending
        assert positions[0].ticker == "AAPL"  # $15500
        assert positions[1].ticker == "GOOGL"  # $6500

    def test_get_positions_with_wash_sale(
        self,
        portfolio_service: PortfolioService,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test positions show wash sale restrictions."""
        # Create a wash sale restriction
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("50"),
            sale_price=Decimal("145.00"),
        )

        positions = portfolio_service.get_positions()
        aapl = next(p for p in positions if p.ticker == "AAPL")

        assert aapl.wash_sale_until is not None
        assert aapl.wash_sale_until == date.today() + timedelta(days=31)

    def test_get_position_found(self, portfolio_service: PortfolioService) -> None:
        """Test getting a specific position."""
        position = portfolio_service.get_position("AAPL")

        assert position is not None
        assert position.ticker == "AAPL"

    def test_get_position_not_found(self, portfolio_service: PortfolioService) -> None:
        """Test getting position that doesn't exist."""
        position = portfolio_service.get_position("MSFT")
        assert position is None

    def test_get_trade_history(self, portfolio_service: PortfolioService) -> None:
        """Test getting trade history."""
        trades = portfolio_service.get_trade_history()

        assert len(trades) == 2
        # Sorted by date descending (GOOGL was more recent)
        assert trades[0].ticker == "GOOGL"
        assert trades[1].ticker == "AAPL"

    def test_get_trade_history_with_filters(self, portfolio_service: PortfolioService) -> None:
        """Test trade history with filters."""
        filters = TradeFilters(ticker="AAPL")
        trades = portfolio_service.get_trade_history(filters=filters)

        assert len(trades) == 1
        assert trades[0].ticker == "AAPL"

    def test_get_trade_history_filter_by_type(self, portfolio_service: PortfolioService) -> None:
        """Test filtering by trade type."""
        filters = TradeFilters(trade_type="sell")
        trades = portfolio_service.get_trade_history(filters=filters)

        # All our mock orders are buys
        assert len(trades) == 0

    def test_get_trade_history_filter_by_date(self, portfolio_service: PortfolioService) -> None:
        """Test filtering by date range."""
        filters = TradeFilters(
            start_date=date.today() - timedelta(days=25),
            end_date=date.today(),
        )
        trades = portfolio_service.get_trade_history(filters=filters)

        # Only GOOGL is within last 25 days
        assert len(trades) == 1
        assert trades[0].ticker == "GOOGL"

    def test_get_alpaca_positions(
        self, portfolio_service: PortfolioService, mock_alpaca: MagicMock
    ) -> None:
        """Test getting raw Alpaca positions."""
        positions = portfolio_service.get_alpaca_positions()

        assert len(positions) == 2
        mock_alpaca.get_positions.assert_called()

    def test_get_alpaca_orders(
        self, portfolio_service: PortfolioService, mock_alpaca: MagicMock
    ) -> None:
        """Test getting raw Alpaca orders."""
        orders = portfolio_service.get_alpaca_orders(days=30)

        assert len(orders) == 2
        mock_alpaca.get_order_history.assert_called_with(days=30)

    def test_get_total_value(self, portfolio_service: PortfolioService) -> None:
        """Test getting total portfolio value."""
        total = portfolio_service.get_total_value()
        assert total == Decimal("22000.00")
