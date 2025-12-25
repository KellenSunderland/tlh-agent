"""Tests for portfolio scanner."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tlh_agent.brokers.alpaca import AlpacaOrder, AlpacaPosition
from tlh_agent.data.local_store import LocalStore
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rules import HarvestRules
from tlh_agent.services.scanner import HarvestOpportunity, PortfolioScanner, ScanResult
from tlh_agent.services.wash_sale import WashSaleService


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalStore:
    """Create a temporary local store."""
    return LocalStore(tmp_path / "state.json")


@pytest.fixture
def wash_sale_service(temp_store: LocalStore) -> WashSaleService:
    """Create wash sale service."""
    return WashSaleService(temp_store)


def make_position(
    symbol: str,
    qty: Decimal,
    avg_entry_price: Decimal,
    current_price: Decimal,
) -> AlpacaPosition:
    """Create a test position."""
    market_value = qty * current_price
    cost_basis = qty * avg_entry_price
    unrealized_pl = market_value - cost_basis
    unrealized_plpc = (unrealized_pl / cost_basis) if cost_basis else Decimal("0")

    return AlpacaPosition(
        symbol=symbol,
        qty=qty,
        avg_entry_price=avg_entry_price,
        current_price=current_price,
        market_value=market_value,
        cost_basis=cost_basis,
        unrealized_pl=unrealized_pl,
        unrealized_plpc=unrealized_plpc,
    )


def make_order(
    symbol: str,
    side: str = "buy",
    filled_at: datetime | None = None,
) -> AlpacaOrder:
    """Create a test order."""
    if filled_at is None:
        filled_at = datetime.now() - timedelta(days=30)

    return AlpacaOrder(
        id=f"order-{symbol}",
        symbol=symbol,
        side=side,
        qty=Decimal("100"),
        filled_qty=Decimal("100"),
        filled_avg_price=Decimal("150.00"),
        status="filled",
        submitted_at=filled_at - timedelta(seconds=10),
        filled_at=filled_at,
    )


@pytest.fixture
def mock_portfolio_service() -> MagicMock:
    """Create mock portfolio service."""
    mock = MagicMock(spec=PortfolioService)

    # Default: one position with loss, one with gain
    # Use smaller positions that fit within 10% portfolio limit
    mock.get_alpaca_positions.return_value = [
        # Loss position: 100 shares, cost $150, current $140 = $1000 loss (6.67%)
        # Market value: $14000
        make_position("AAPL", Decimal("100"), Decimal("150"), Decimal("140")),
        # Gain position: 50 shares, cost $100, current $120 = $1000 gain
        make_position("GOOGL", Decimal("50"), Decimal("100"), Decimal("120")),
    ]

    # Order history (bought 30 days ago)
    mock.get_alpaca_orders.return_value = [
        make_order("AAPL"),
        make_order("GOOGL"),
    ]

    # Total portfolio value: large enough for 10% limit to include positions
    # 10% of $200000 = $20000, which covers the $14000 AAPL position
    mock.get_total_value.return_value = Decimal("200000")

    return mock


@pytest.fixture
def scanner(
    mock_portfolio_service: MagicMock,
    wash_sale_service: WashSaleService,
    temp_store: LocalStore,
) -> PortfolioScanner:
    """Create scanner with mocks."""
    return PortfolioScanner(
        portfolio_service=mock_portfolio_service,
        wash_sale_service=wash_sale_service,
        store=temp_store,
    )


class TestHarvestOpportunity:
    """Tests for HarvestOpportunity dataclass."""

    def test_can_harvest_new(self) -> None:
        """Test new opportunity can be harvested."""
        opp = HarvestOpportunity(
            ticker="AAPL",
            shares=Decimal("100"),
            current_price=Decimal("140"),
            avg_cost=Decimal("150"),
            market_value=Decimal("14000"),
            cost_basis=Decimal("15000"),
            unrealized_loss=Decimal("-1000"),
            loss_pct=Decimal("6.67"),
            estimated_tax_benefit=Decimal("350"),
            days_held=30,
            queue_status=None,
        )
        assert opp.can_harvest is True

    def test_can_harvest_pending(self) -> None:
        """Test pending opportunity can still be harvested."""
        opp = HarvestOpportunity(
            ticker="AAPL",
            shares=Decimal("100"),
            current_price=Decimal("140"),
            avg_cost=Decimal("150"),
            market_value=Decimal("14000"),
            cost_basis=Decimal("15000"),
            unrealized_loss=Decimal("-1000"),
            loss_pct=Decimal("6.67"),
            estimated_tax_benefit=Decimal("350"),
            days_held=30,
            queue_status="pending",
        )
        assert opp.can_harvest is True

    def test_can_harvest_approved_false(self) -> None:
        """Test approved opportunity cannot be harvested again."""
        opp = HarvestOpportunity(
            ticker="AAPL",
            shares=Decimal("100"),
            current_price=Decimal("140"),
            avg_cost=Decimal("150"),
            market_value=Decimal("14000"),
            cost_basis=Decimal("15000"),
            unrealized_loss=Decimal("-1000"),
            loss_pct=Decimal("6.67"),
            estimated_tax_benefit=Decimal("350"),
            days_held=30,
            queue_status="approved",
        )
        assert opp.can_harvest is False


class TestPortfolioScanner:
    """Tests for PortfolioScanner."""

    def test_scan_finds_opportunities(self, scanner: PortfolioScanner) -> None:
        """Test scan finds loss positions."""
        result = scanner.scan()

        assert isinstance(result, ScanResult)
        assert len(result.opportunities) == 1
        assert result.opportunities[0].ticker == "AAPL"
        assert result.positions_scanned == 2
        assert result.positions_with_loss == 1

    def test_scan_calculates_benefit(self, scanner: PortfolioScanner) -> None:
        """Test tax benefit calculation."""
        result = scanner.scan()

        opp = result.opportunities[0]
        # $1000 loss * 35% tax rate = $350 benefit
        assert opp.estimated_tax_benefit == Decimal("350.00")
        assert result.total_potential_benefit == Decimal("350.00")

    def test_scan_excludes_wash_restricted(
        self,
        scanner: PortfolioScanner,
        wash_sale_service: WashSaleService,
    ) -> None:
        """Test scan excludes wash sale restricted positions."""
        # Create a restriction for AAPL
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("50"),
            sale_price=Decimal("145"),
        )

        result = scanner.scan()

        assert len(result.opportunities) == 0
        assert result.positions_restricted == 1

    def test_scan_excludes_gains(
        self, scanner: PortfolioScanner, mock_portfolio_service: MagicMock
    ) -> None:
        """Test scan excludes positions with gains."""
        # All positions have gains
        mock_portfolio_service.get_alpaca_positions.return_value = [
            make_position("AAPL", Decimal("100"), Decimal("100"), Decimal("120")),
            make_position("GOOGL", Decimal("50"), Decimal("100"), Decimal("110")),
        ]

        result = scanner.scan()

        assert len(result.opportunities) == 0
        assert result.positions_with_loss == 0

    def test_scan_excludes_below_threshold(
        self, scanner: PortfolioScanner, mock_portfolio_service: MagicMock
    ) -> None:
        """Test scan excludes positions below loss threshold."""
        # Small loss that doesn't meet thresholds
        mock_portfolio_service.get_alpaca_positions.return_value = [
            # $50 loss, 1% - below both thresholds
            make_position("AAPL", Decimal("10"), Decimal("500"), Decimal("495")),
        ]

        result = scanner.scan()

        assert len(result.opportunities) == 0

    def test_scan_excludes_recent_buys(
        self, scanner: PortfolioScanner, mock_portfolio_service: MagicMock
    ) -> None:
        """Test scan excludes recently purchased positions."""
        # Position bought only 3 days ago
        mock_portfolio_service.get_alpaca_orders.return_value = [
            make_order("AAPL", filled_at=datetime.now() - timedelta(days=3)),
        ]

        result = scanner.scan()

        assert len(result.opportunities) == 0

    def test_scan_sorts_by_benefit(
        self, scanner: PortfolioScanner, mock_portfolio_service: MagicMock
    ) -> None:
        """Test opportunities sorted by tax benefit."""
        mock_portfolio_service.get_alpaca_positions.return_value = [
            # Small loss: $200 = $70 benefit (meets $50 minimum)
            make_position("AAPL", Decimal("20"), Decimal("150"), Decimal("140")),
            # Large loss: $1000 = $350 benefit
            make_position("NVDA", Decimal("100"), Decimal("150"), Decimal("140")),
            # Medium loss: $500 = $175 benefit
            make_position("TSLA", Decimal("50"), Decimal("150"), Decimal("140")),
        ]
        mock_portfolio_service.get_alpaca_orders.return_value = [
            make_order("AAPL"),
            make_order("NVDA"),
            make_order("TSLA"),
        ]
        # Large portfolio so all positions fit within 10% limit
        mock_portfolio_service.get_total_value.return_value = Decimal("250000")

        result = scanner.scan()

        assert len(result.opportunities) == 3
        # Sorted by benefit descending
        assert result.opportunities[0].ticker == "NVDA"  # $350
        assert result.opportunities[1].ticker == "TSLA"  # $175
        assert result.opportunities[2].ticker == "AAPL"  # $70

    def test_scan_applies_portfolio_limit(
        self, scanner: PortfolioScanner, mock_portfolio_service: MagicMock
    ) -> None:
        """Test portfolio percentage limit is applied."""
        # Two large positions that exceed 10% limit together
        # Position A: $5000, Position B: $8000 = $13000 total
        # With 10% of $100000 = $10000 limit, only first should fit
        mock_portfolio_service.get_alpaca_positions.return_value = [
            # $5000 position with $500 loss (10%)
            make_position("AAPL", Decimal("50"), Decimal("110"), Decimal("100")),
            # $8000 position with $1000 loss (12.5%)
            make_position("NVDA", Decimal("80"), Decimal("112.50"), Decimal("100")),
        ]
        mock_portfolio_service.get_alpaca_orders.return_value = [
            make_order("AAPL"),
            make_order("NVDA"),
        ]
        # 10% of $100000 = $10000 limit
        mock_portfolio_service.get_total_value.return_value = Decimal("100000")

        result = scanner.scan()

        # NVDA has higher benefit so it comes first, fits in $10000
        # AAPL ($5000) would push total to $13000, exceeding limit
        assert len(result.opportunities) == 1
        assert result.opportunities[0].ticker == "NVDA"

    def test_scan_with_custom_rules(
        self, mock_portfolio_service: MagicMock, temp_store: LocalStore
    ) -> None:
        """Test scanner with custom rules."""
        # Ensure portfolio value is large enough for the limit
        mock_portfolio_service.get_total_value.return_value = Decimal("200000")

        wash_sale = WashSaleService(temp_store)
        rules = HarvestRules(
            min_loss_usd=Decimal("50"),  # Lower threshold
            min_loss_pct=Decimal("1.0"),  # Lower threshold
            max_harvest_pct=Decimal("50.0"),  # Higher limit
        )
        scanner = PortfolioScanner(mock_portfolio_service, wash_sale, temp_store, rules)

        result = scanner.scan()

        assert len(result.opportunities) == 1

    def test_add_to_queue(self, scanner: PortfolioScanner) -> None:
        """Test adding opportunity to queue."""
        result = scanner.scan()
        opp = result.opportunities[0]

        queue_item = scanner.add_to_queue(opp)

        assert queue_item.ticker == "AAPL"
        assert queue_item.status == "pending"
        assert scanner.get_pending_harvests()[0].id == queue_item.id

    def test_approve_harvest(self, scanner: PortfolioScanner, temp_store: LocalStore) -> None:
        """Test approving a queued harvest."""
        result = scanner.scan()
        opp = result.opportunities[0]
        queue_item = scanner.add_to_queue(opp)

        scanner.approve_harvest(queue_item.id)

        approved = scanner.get_approved_harvests()
        assert len(approved) == 1
        assert approved[0].status == "approved"

    def test_reject_harvest(self, scanner: PortfolioScanner, temp_store: LocalStore) -> None:
        """Test rejecting a queued harvest."""
        result = scanner.scan()
        opp = result.opportunities[0]
        queue_item = scanner.add_to_queue(opp)

        scanner.reject_harvest(queue_item.id)

        # Should not be in pending or approved
        assert len(scanner.get_pending_harvests()) == 0
        assert len(scanner.get_approved_harvests()) == 0
        # But should still be in queue with rejected status
        all_items = temp_store.get_harvest_queue()
        assert len(all_items) == 1
        assert all_items[0].status == "rejected"

    def test_approve_invalid_id(self, scanner: PortfolioScanner) -> None:
        """Test approving non-existent item raises error."""
        with pytest.raises(ValueError, match="Queue item not found"):
            scanner.approve_harvest("invalid-id")

    def test_update_rules(self, scanner: PortfolioScanner) -> None:
        """Test updating scanner rules."""
        new_rules = HarvestRules(min_loss_usd=Decimal("500"))
        scanner.update_rules(new_rules)

        assert scanner.rules.min_loss_usd == Decimal("500")

    def test_scan_shows_queue_status(
        self, scanner: PortfolioScanner, temp_store: LocalStore
    ) -> None:
        """Test scan shows items already in queue."""
        # First scan and queue
        result1 = scanner.scan()
        scanner.add_to_queue(result1.opportunities[0])

        # Second scan should show queue status
        result2 = scanner.scan()

        assert len(result2.opportunities) == 1
        assert result2.opportunities[0].queue_status == "pending"
