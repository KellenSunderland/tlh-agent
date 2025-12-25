"""Tests for local JSON storage."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tlh_agent.data.local_store import (
    HarvestQueueItem,
    LocalStore,
    LossLedgerYear,
    WashSaleRestriction,
)


@pytest.fixture
def temp_store(tmp_path: Path) -> LocalStore:
    """Create a temporary local store."""
    return LocalStore(tmp_path / "state.json")


class TestWashSaleRestriction:
    """Tests for WashSaleRestriction dataclass."""

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "id": "test-id",
            "ticker": "AAPL",
            "shares_sold": "100",
            "sale_price": "150.00",
            "sale_date": "2024-12-01",
            "restriction_end": "2025-01-01",
            "rebuy_status": "pending",
        }
        restriction = WashSaleRestriction.from_dict(data)

        assert restriction.id == "test-id"
        assert restriction.ticker == "AAPL"
        assert restriction.shares_sold == Decimal("100")
        assert restriction.sale_price == Decimal("150.00")
        assert restriction.sale_date == date(2024, 12, 1)
        assert restriction.restriction_end == date(2025, 1, 1)

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        restriction = WashSaleRestriction(
            id="test-id",
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150.00"),
            sale_date=date(2024, 12, 1),
            restriction_end=date(2025, 1, 1),
        )
        data = restriction.to_dict()

        assert data["id"] == "test-id"
        assert data["ticker"] == "AAPL"
        assert data["shares_sold"] == "100"
        assert data["sale_date"] == "2024-12-01"

    def test_days_remaining(self) -> None:
        """Test days_remaining calculation."""
        future_date = date.today() + timedelta(days=10)
        restriction = WashSaleRestriction(
            id="test",
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today(),
            restriction_end=future_date,
        )
        assert restriction.days_remaining == 10

    def test_is_active(self) -> None:
        """Test is_active property."""
        # Future end date = active
        future = WashSaleRestriction(
            id="test",
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today() - timedelta(days=30),
            restriction_end=date.today() + timedelta(days=1),
        )
        assert future.is_active is True

        # Past end date = not active
        past = WashSaleRestriction(
            id="test",
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today() - timedelta(days=60),
            restriction_end=date.today() - timedelta(days=1),
        )
        assert past.is_active is False


class TestLossLedgerYear:
    """Tests for LossLedgerYear dataclass."""

    def test_default_values(self) -> None:
        """Test default zero values."""
        ledger = LossLedgerYear()
        assert ledger.short_term_losses == Decimal("0")
        assert ledger.long_term_losses == Decimal("0")
        assert ledger.total_losses == Decimal("0")

    def test_total_losses(self) -> None:
        """Test total_losses calculation."""
        ledger = LossLedgerYear(
            short_term_losses=Decimal("1000"),
            long_term_losses=Decimal("500"),
        )
        assert ledger.total_losses == Decimal("1500")


class TestHarvestQueueItem:
    """Tests for HarvestQueueItem dataclass."""

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "id": "harvest-1",
            "ticker": "NVDA",
            "shares": "50",
            "current_price": "400.00",
            "cost_basis": "450.00",
            "unrealized_loss": "-2500.00",
            "estimated_tax_benefit": "875.00",
            "status": "pending",
            "created_at": "2024-12-24T10:00:00",
        }
        item = HarvestQueueItem.from_dict(data)

        assert item.id == "harvest-1"
        assert item.ticker == "NVDA"
        assert item.shares == Decimal("50")
        assert item.unrealized_loss == Decimal("-2500.00")
        assert item.status == "pending"


class TestLocalStore:
    """Tests for LocalStore class."""

    def test_creates_file_on_save(self, temp_store: LocalStore) -> None:
        """Test that file is created when saving."""
        restriction = WashSaleRestriction(
            id=temp_store.new_id(),
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today(),
            restriction_end=date.today() + timedelta(days=31),
        )
        temp_store.add_restriction(restriction)

        assert temp_store._path.exists()

    def test_add_and_get_restrictions(self, temp_store: LocalStore) -> None:
        """Test adding and retrieving restrictions."""
        restriction = WashSaleRestriction(
            id=temp_store.new_id(),
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today(),
            restriction_end=date.today() + timedelta(days=31),
        )
        temp_store.add_restriction(restriction)

        restrictions = temp_store.get_restrictions()
        assert len(restrictions) == 1
        assert restrictions[0].ticker == "AAPL"

    def test_get_active_restrictions(self, temp_store: LocalStore) -> None:
        """Test filtering active restrictions."""
        # Active restriction
        temp_store.add_restriction(
            WashSaleRestriction(
                id=temp_store.new_id(),
                ticker="AAPL",
                shares_sold=Decimal("100"),
                sale_price=Decimal("150"),
                sale_date=date.today(),
                restriction_end=date.today() + timedelta(days=31),
            )
        )
        # Expired restriction
        temp_store.add_restriction(
            WashSaleRestriction(
                id=temp_store.new_id(),
                ticker="GOOGL",
                shares_sold=Decimal("50"),
                sale_price=Decimal("100"),
                sale_date=date.today() - timedelta(days=60),
                restriction_end=date.today() - timedelta(days=1),
            )
        )

        active = temp_store.get_active_restrictions()
        assert len(active) == 1
        assert active[0].ticker == "AAPL"

    def test_get_restriction_by_ticker(self, temp_store: LocalStore) -> None:
        """Test getting restriction by ticker."""
        temp_store.add_restriction(
            WashSaleRestriction(
                id=temp_store.new_id(),
                ticker="AAPL",
                shares_sold=Decimal("100"),
                sale_price=Decimal("150"),
                sale_date=date.today(),
                restriction_end=date.today() + timedelta(days=31),
            )
        )

        found = temp_store.get_restriction_by_ticker("AAPL")
        assert found is not None
        assert found.ticker == "AAPL"

        not_found = temp_store.get_restriction_by_ticker("GOOGL")
        assert not_found is None

    def test_update_restriction(self, temp_store: LocalStore) -> None:
        """Test updating a restriction."""
        restriction = WashSaleRestriction(
            id=temp_store.new_id(),
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
            sale_date=date.today(),
            restriction_end=date.today() + timedelta(days=31),
        )
        temp_store.add_restriction(restriction)

        # Update it
        restriction.rebuy_status = "completed"
        restriction.rebuy_date = date.today()
        restriction.rebuy_price = Decimal("155.00")
        temp_store.update_restriction(restriction)

        # Verify update
        updated = temp_store.get_restrictions()[0]
        assert updated.rebuy_status == "completed"
        assert updated.rebuy_price == Decimal("155.00")

    def test_loss_ledger_operations(self, temp_store: LocalStore) -> None:
        """Test loss ledger CRUD."""
        # Initially empty
        ledger = temp_store.get_loss_ledger()
        assert len(ledger) == 0

        # Add entry
        entry = LossLedgerYear(
            short_term_losses=Decimal("1000"),
            long_term_losses=Decimal("500"),
            carryforward=Decimal("1500"),
        )
        temp_store.update_loss_ledger_year(2024, entry)

        # Retrieve
        retrieved = temp_store.get_loss_ledger_year(2024)
        assert retrieved.short_term_losses == Decimal("1000")
        assert retrieved.carryforward == Decimal("1500")

        # Get year that doesn't exist
        empty = temp_store.get_loss_ledger_year(2020)
        assert empty.total_losses == Decimal("0")

    def test_harvest_queue_operations(self, temp_store: LocalStore) -> None:
        """Test harvest queue CRUD."""
        item = HarvestQueueItem(
            id=temp_store.new_id(),
            ticker="NVDA",
            shares=Decimal("50"),
            current_price=Decimal("400"),
            cost_basis=Decimal("450"),
            unrealized_loss=Decimal("-2500"),
            estimated_tax_benefit=Decimal("875"),
        )
        temp_store.add_harvest_item(item)

        # Verify added
        queue = temp_store.get_harvest_queue()
        assert len(queue) == 1
        assert queue[0].ticker == "NVDA"

        # Check pending
        pending = temp_store.get_pending_harvests()
        assert len(pending) == 1

        # Approve and check
        item.status = "approved"
        temp_store.update_harvest_item(item)

        approved = temp_store.get_approved_harvests()
        assert len(approved) == 1
        assert temp_store.get_pending_harvests() == []

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """Test that data persists across store instances."""
        path = tmp_path / "state.json"

        # Write with first instance
        store1 = LocalStore(path)
        store1.add_restriction(
            WashSaleRestriction(
                id=store1.new_id(),
                ticker="AAPL",
                shares_sold=Decimal("100"),
                sale_price=Decimal("150"),
                sale_date=date.today(),
                restriction_end=date.today() + timedelta(days=31),
            )
        )

        # Read with second instance
        store2 = LocalStore(path)
        restrictions = store2.get_restrictions()
        assert len(restrictions) == 1
        assert restrictions[0].ticker == "AAPL"

    def test_new_id_uniqueness(self, temp_store: LocalStore) -> None:
        """Test that new_id generates unique IDs."""
        ids = {temp_store.new_id() for _ in range(100)}
        assert len(ids) == 100
