"""Tests for Alpaca broker client."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from tlh_agent.brokers.alpaca import AlpacaClient


class MockPosition:
    """Mock Alpaca position object."""

    def __init__(
        self,
        symbol: str = "AAPL",
        qty: str = "100",
        avg_entry_price: str = "150.00",
        current_price: str = "160.00",
        market_value: str = "16000.00",
        cost_basis: str = "15000.00",
        unrealized_pl: str = "1000.00",
        unrealized_plpc: str = "0.0667",
    ):
        self.symbol = symbol
        self.qty = qty
        self.avg_entry_price = avg_entry_price
        self.current_price = current_price
        self.market_value = market_value
        self.cost_basis = cost_basis
        self.unrealized_pl = unrealized_pl
        self.unrealized_plpc = unrealized_plpc


class MockOrder:
    """Mock Alpaca order object."""

    def __init__(
        self,
        id: str = "order-123",
        symbol: str = "AAPL",
        side=None,
        qty: str = "100",
        filled_qty: str = "100",
        filled_avg_price: str = "150.00",
        status=None,
        submitted_at: datetime | None = None,
        filled_at: datetime | None = None,
    ):
        from alpaca.trading.enums import OrderSide, OrderStatus

        self.id = id
        self.symbol = symbol
        self.side = side or OrderSide.BUY
        self.qty = qty
        self.filled_qty = filled_qty
        self.filled_avg_price = filled_avg_price
        self.status = status or OrderStatus.FILLED
        self.submitted_at = submitted_at or datetime.now()
        self.filled_at = filled_at or datetime.now()


class MockAccount:
    """Mock Alpaca account object."""

    def __init__(self):
        from alpaca.trading.enums import AccountStatus

        self.id = "account-123"
        self.status = AccountStatus.ACTIVE
        self.equity = "100000.00"
        self.cash = "25000.00"
        self.buying_power = "50000.00"


@pytest.fixture
def mock_trading_client():
    """Create a mock TradingClient."""
    with patch("tlh_agent.brokers.alpaca.TradingClient") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


class TestAlpacaClient:
    """Tests for AlpacaClient class."""

    def test_init_paper_mode(self, mock_trading_client: MagicMock) -> None:
        """Test client initializes in paper mode by default."""
        client = AlpacaClient(api_key="key", secret_key="secret")
        assert client.is_paper is True

    def test_init_live_mode(self, mock_trading_client: MagicMock) -> None:
        """Test client can be initialized in live mode."""
        client = AlpacaClient(api_key="key", secret_key="secret", paper=False)
        assert client.is_paper is False

    def test_get_account(self, mock_trading_client: MagicMock) -> None:
        """Test getting account information."""
        mock_trading_client.get_account.return_value = MockAccount()

        client = AlpacaClient(api_key="key", secret_key="secret")
        account = client.get_account()

        assert account.id == "account-123"
        assert account.status == "ACTIVE"
        assert account.equity == Decimal("100000.00")
        assert account.cash == Decimal("25000.00")
        assert account.buying_power == Decimal("50000.00")

    def test_get_positions(self, mock_trading_client: MagicMock) -> None:
        """Test getting all positions."""
        mock_trading_client.get_all_positions.return_value = [
            MockPosition(symbol="AAPL", qty="100"),
            MockPosition(symbol="GOOGL", qty="50"),
        ]

        client = AlpacaClient(api_key="key", secret_key="secret")
        positions = client.get_positions()

        assert len(positions) == 2
        assert positions[0].symbol == "AAPL"
        assert positions[0].qty == Decimal("100")
        assert positions[1].symbol == "GOOGL"
        assert positions[1].qty == Decimal("50")

    def test_get_positions_empty(self, mock_trading_client: MagicMock) -> None:
        """Test getting positions when none exist."""
        mock_trading_client.get_all_positions.return_value = []

        client = AlpacaClient(api_key="key", secret_key="secret")
        positions = client.get_positions()

        assert len(positions) == 0

    def test_position_decimal_conversion(self, mock_trading_client: MagicMock) -> None:
        """Test that position values are properly converted to Decimal."""
        mock_trading_client.get_all_positions.return_value = [
            MockPosition(
                symbol="AAPL",
                qty="100.5",
                avg_entry_price="150.25",
                current_price="160.75",
                market_value="16155.38",
                cost_basis="15100.13",
                unrealized_pl="1055.25",
                unrealized_plpc="0.0699",
            ),
        ]

        client = AlpacaClient(api_key="key", secret_key="secret")
        positions = client.get_positions()

        pos = positions[0]
        assert pos.qty == Decimal("100.5")
        assert pos.avg_entry_price == Decimal("150.25")
        assert pos.current_price == Decimal("160.75")
        assert pos.market_value == Decimal("16155.38")
        assert pos.cost_basis == Decimal("15100.13")
        assert pos.unrealized_pl == Decimal("1055.25")

    def test_get_order_history(self, mock_trading_client: MagicMock) -> None:
        """Test getting order history."""
        mock_trading_client.get_orders.return_value = [
            MockOrder(id="order-1", symbol="AAPL"),
            MockOrder(id="order-2", symbol="GOOGL"),
        ]

        client = AlpacaClient(api_key="key", secret_key="secret")
        orders = client.get_order_history(days=30)

        assert len(orders) == 2
        assert orders[0].id == "order-1"
        assert orders[0].symbol == "AAPL"

    def test_submit_market_order(self, mock_trading_client: MagicMock) -> None:
        """Test submitting a market order."""
        mock_trading_client.submit_order.return_value = MockOrder(
            id="new-order",
            symbol="AAPL",
            qty="100",
        )

        client = AlpacaClient(api_key="key", secret_key="secret")
        order = client.submit_market_order(
            symbol="AAPL",
            qty=Decimal("100"),
            side="buy",
        )

        assert order.id == "new-order"
        assert order.symbol == "AAPL"
        mock_trading_client.submit_order.assert_called_once()

    def test_submit_limit_order(self, mock_trading_client: MagicMock) -> None:
        """Test submitting a limit order."""
        mock_trading_client.submit_order.return_value = MockOrder(
            id="limit-order",
            symbol="AAPL",
        )

        client = AlpacaClient(api_key="key", secret_key="secret")
        order = client.submit_limit_order(
            symbol="AAPL",
            qty=Decimal("100"),
            side="sell",
            limit_price=Decimal("150.00"),
        )

        assert order.id == "limit-order"
        mock_trading_client.submit_order.assert_called_once()

    def test_cancel_order_success(self, mock_trading_client: MagicMock) -> None:
        """Test cancelling an order successfully."""
        mock_trading_client.cancel_order_by_id.return_value = None

        client = AlpacaClient(api_key="key", secret_key="secret")
        result = client.cancel_order("order-123")

        assert result is True

    def test_cancel_order_failure(self, mock_trading_client: MagicMock) -> None:
        """Test cancelling an order that fails."""
        mock_trading_client.cancel_order_by_id.side_effect = Exception("Order not found")

        client = AlpacaClient(api_key="key", secret_key="secret")
        result = client.cancel_order("bad-order")

        assert result is False
