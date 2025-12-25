"""Tests for wash sale service."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tlh_agent.data.local_store import LocalStore
from tlh_agent.services.wash_sale import WashSaleService


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalStore:
    """Create a temporary local store."""
    return LocalStore(tmp_path / "state.json")


@pytest.fixture
def wash_sale_service(temp_store: LocalStore) -> WashSaleService:
    """Create wash sale service with temp store."""
    return WashSaleService(temp_store)


class TestWashSaleService:
    """Tests for WashSaleService."""

    def test_create_restriction(self, wash_sale_service: WashSaleService) -> None:
        """Test creating a wash sale restriction."""
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        assert restriction.ticker == "AAPL"
        assert restriction.shares_sold == Decimal("100")
        assert restriction.sale_price == Decimal("150.00")
        assert restriction.sale_date == date.today()
        assert restriction.rebuy_status == "pending"
        # Restriction ends 31 days after sale
        assert restriction.restriction_end == date.today() + timedelta(days=31)

    def test_is_restricted(self, wash_sale_service: WashSaleService) -> None:
        """Test checking if ticker is restricted."""
        # Not restricted initially
        assert wash_sale_service.is_restricted("AAPL") is False

        # Create restriction
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        # Now restricted
        assert wash_sale_service.is_restricted("AAPL") is True
        # Other tickers not restricted
        assert wash_sale_service.is_restricted("GOOGL") is False

    def test_get_restriction(self, wash_sale_service: WashSaleService) -> None:
        """Test getting restriction by ticker."""
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        restriction = wash_sale_service.get_restriction("AAPL")
        assert restriction is not None
        assert restriction.ticker == "AAPL"

        # Non-existent ticker
        assert wash_sale_service.get_restriction("GOOGL") is None

    def test_get_active_restrictions(self, wash_sale_service: WashSaleService) -> None:
        """Test getting all active restrictions."""
        wash_sale_service.create_restriction("AAPL", Decimal("100"), Decimal("150"))
        wash_sale_service.create_restriction("GOOGL", Decimal("50"), Decimal("100"))

        active = wash_sale_service.get_active_restrictions()
        assert len(active) == 2
        tickers = {r.ticker for r in active}
        assert tickers == {"AAPL", "GOOGL"}

    def test_get_clear_date(self, wash_sale_service: WashSaleService) -> None:
        """Test getting the clear date for a ticker."""
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        clear_date = wash_sale_service.get_clear_date("AAPL")
        assert clear_date == date.today() + timedelta(days=31)

        # Non-restricted ticker
        assert wash_sale_service.get_clear_date("GOOGL") is None

    def test_days_until_clear(self, wash_sale_service: WashSaleService) -> None:
        """Test getting days until clear."""
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        days = wash_sale_service.days_until_clear("AAPL")
        assert days == 31

        # Non-restricted ticker
        assert wash_sale_service.days_until_clear("GOOGL") is None

    def test_mark_rebuy_complete(
        self, wash_sale_service: WashSaleService, temp_store: LocalStore
    ) -> None:
        """Test marking rebuy as complete."""
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
            # Use old date so restriction is expired
            sale_date=date.today() - timedelta(days=40),
        )

        wash_sale_service.mark_rebuy_complete(
            restriction_id=restriction.id,
            rebuy_price=Decimal("155.00"),
        )

        # Verify updated
        updated = temp_store.get_restrictions()[0]
        assert updated.rebuy_status == "completed"
        assert updated.rebuy_price == Decimal("155.00")
        assert updated.rebuy_date == date.today()

    def test_mark_rebuy_skipped(
        self, wash_sale_service: WashSaleService, temp_store: LocalStore
    ) -> None:
        """Test marking rebuy as skipped."""
        restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        wash_sale_service.mark_rebuy_skipped(restriction.id)

        updated = temp_store.get_restrictions()[0]
        assert updated.rebuy_status == "skipped"

    def test_get_pending_rebuys(
        self, wash_sale_service: WashSaleService, temp_store: LocalStore
    ) -> None:
        """Test getting pending rebuys."""
        # Create restriction that's expired (ready for rebuy)
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
            sale_date=date.today() - timedelta(days=40),
        )

        # Create restriction that's still active
        wash_sale_service.create_restriction(
            ticker="GOOGL",
            shares_sold=Decimal("50"),
            sale_price=Decimal("100.00"),
        )

        pending = wash_sale_service.get_pending_rebuys()
        assert len(pending) == 1
        assert pending[0].ticker == "AAPL"

    def test_would_violate_future_buy(
        self, wash_sale_service: WashSaleService
    ) -> None:
        """Test checking if a buy would violate wash sale rules."""
        # Create a sale
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
        )

        # Buying today would violate
        assert wash_sale_service.would_violate("AAPL") is True
        assert wash_sale_service.would_violate("AAPL", date.today()) is True

        # Buying in 15 days would violate
        assert wash_sale_service.would_violate("AAPL", date.today() + timedelta(days=15)) is True

        # Buying in 35 days would not violate
        assert wash_sale_service.would_violate("AAPL", date.today() + timedelta(days=35)) is False

        # Different ticker never violates
        assert wash_sale_service.would_violate("GOOGL") is False

    def test_would_violate_past_sale(
        self, wash_sale_service: WashSaleService
    ) -> None:
        """Test violation check for buys that happen before a sale."""
        # Create a sale that happened 20 days ago
        sale_date = date.today() - timedelta(days=20)
        wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
            sale_date=sale_date,
        )

        # A buy 10 days before the sale (30 days ago) would violate
        buy_date = date.today() - timedelta(days=30)
        assert wash_sale_service.would_violate("AAPL", buy_date) is True

        # A buy 40 days before the sale would not violate
        buy_date = date.today() - timedelta(days=60)
        assert wash_sale_service.would_violate("AAPL", buy_date) is False

    def test_cleanup_old_restrictions(
        self, wash_sale_service: WashSaleService, temp_store: LocalStore
    ) -> None:
        """Test cleaning up old completed restrictions."""
        # Create old completed restriction
        old_restriction = wash_sale_service.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
            sale_date=date.today() - timedelta(days=120),
        )
        wash_sale_service.mark_rebuy_complete(old_restriction.id, Decimal("155"))

        # Create recent restriction
        wash_sale_service.create_restriction(
            ticker="GOOGL",
            shares_sold=Decimal("50"),
            sale_price=Decimal("100.00"),
        )

        # Cleanup
        removed = wash_sale_service.cleanup_old_restrictions(days_old=90)
        assert removed == 1

        # Only GOOGL remains
        restrictions = temp_store.get_restrictions()
        assert len(restrictions) == 1
        assert restrictions[0].ticker == "GOOGL"
