"""Pytest fixtures for UI testing."""

import contextlib
import os
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tlh_agent.app import TLHAgentApp
from tlh_agent.data.local_store import LossLedgerYear, WashSaleRestriction
from tlh_agent.services import ServiceProvider
from tlh_agent.services.portfolio import PortfolioSummary, Position
from tlh_agent.services.scanner import HarvestOpportunity, ScanResult
from tlh_agent.ui.main_window import MainWindow


def _create_mock_services():
    """Create mock services with test data."""
    # Mock portfolio service
    mock_portfolio = MagicMock()
    mock_portfolio.get_portfolio_summary.return_value = PortfolioSummary(
        total_value=Decimal("523847.32"),
        total_cost_basis=Decimal("498234.18"),
        unrealized_gain_loss=Decimal("25613.14"),
        unrealized_gain_loss_pct=Decimal("5.14"),
        ytd_harvested_losses=Decimal("-12456.78"),
        pending_harvest_opportunities=5,
        active_wash_sale_restrictions=3,
    )
    mock_portfolio.get_positions.return_value = [
        Position(
            ticker="AAPL",
            name="Apple Inc.",
            shares=Decimal("50"),
            avg_cost_per_share=Decimal("150.35"),
            current_price=Decimal("195.50"),
            market_value=Decimal("9775.00"),
            cost_basis=Decimal("7517.50"),
            unrealized_gain_loss=Decimal("2257.50"),
            unrealized_gain_loss_pct=Decimal("30.03"),
        ),
        Position(
            ticker="MSFT",
            name="Microsoft Corporation",
            shares=Decimal("40"),
            avg_cost_per_share=Decimal("285.00"),
            current_price=Decimal("378.50"),
            market_value=Decimal("15140.00"),
            cost_basis=Decimal("11400.00"),
            unrealized_gain_loss=Decimal("3740.00"),
            unrealized_gain_loss_pct=Decimal("32.81"),
            wash_sale_until=date.today() + timedelta(days=12),
        ),
    ]
    mock_portfolio.get_trade_history.return_value = []

    # Mock scanner
    mock_scanner = MagicMock()
    mock_scanner.scan.return_value = ScanResult(
        opportunities=[
            HarvestOpportunity(
                ticker="NVDA",
                shares=Decimal("30"),
                current_price=Decimal("485.00"),
                avg_cost=Decimal("520.00"),
                market_value=Decimal("14550.00"),
                cost_basis=Decimal("15600.00"),
                unrealized_loss=Decimal("-1050.00"),
                loss_pct=Decimal("-6.73"),
                estimated_tax_benefit=Decimal("367.50"),
                days_held=90,
                queue_status="pending",
            ),
        ],
        total_potential_benefit=Decimal("367.50"),
        positions_scanned=10,
        positions_with_loss=3,
        positions_restricted=1,
    )

    # Mock wash sale service
    mock_wash_sale = MagicMock()
    today = date.today()
    mock_wash_sale.get_active_restrictions.return_value = [
        WashSaleRestriction(
            id="r1",
            ticker="MSFT",
            shares_sold=Decimal("40"),
            sale_price=Decimal("375.20"),
            sale_date=today - timedelta(days=18),
            restriction_end=today + timedelta(days=12),
        ),
    ]

    # Mock store with loss ledger
    # The UI expects entries to have a 'year' field, so create mock objects
    mock_store = MagicMock()

    entry_2024 = LossLedgerYear(
        short_term_losses=Decimal("12456.78"),
        long_term_losses=Decimal("3200.00"),
        used_against_gains=Decimal("7422.22"),
        carryforward=Decimal("8234.56"),
    )
    entry_2024.year = 2024  # Add year attribute for UI

    entry_2023 = LossLedgerYear(
        short_term_losses=Decimal("8900.00"),
        long_term_losses=Decimal("2100.00"),
        used_against_gains=Decimal("11000.00"),
        carryforward=Decimal("0.00"),
    )
    entry_2023.year = 2023

    mock_store.get_loss_ledger.return_value = {
        2024: entry_2024,
        2023: entry_2023,
    }
    mock_store.get_pending_harvests.return_value = []

    return mock_portfolio, mock_scanner, mock_wash_sale, mock_store

# Directory for screenshots
SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots"


@pytest.fixture(scope="module")
def screenshots_dir() -> Path:
    """Create and return the screenshots directory."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    return SCREENSHOTS_DIR


@pytest.fixture
def app(request):
    """Create a TLH Agent app instance for testing.

    The app is automatically destroyed after the test.
    Injects mock services with test data.
    """
    # Skip if no display available (CI environment)
    if os.environ.get("DISPLAY") is None and os.name != "nt":
        # Check if we're on macOS which doesn't need DISPLAY
        import platform

        if platform.system() != "Darwin":
            pytest.skip("No display available")

    # Create mock services
    mock_portfolio, mock_scanner, mock_wash_sale, mock_store = _create_mock_services()

    # Patch ServiceProvider.create to inject mock services
    original_create = ServiceProvider.create

    def mock_create(config_dir=None, connect_alpaca=True):
        # Create base provider without Alpaca
        provider = original_create(config_dir=config_dir, connect_alpaca=False)
        # Inject mock services to simulate live mode
        provider.alpaca = MagicMock()  # Make is_live return True
        provider.portfolio = mock_portfolio
        provider.scanner = mock_scanner
        provider.wash_sale = mock_wash_sale
        provider.store = mock_store
        return provider

    with patch.object(ServiceProvider, "create", mock_create):
        app_instance = TLHAgentApp()

        yield app_instance

        # Cleanup
        with contextlib.suppress(tk.TclError):
            app_instance.root.destroy()


@pytest.fixture
def main_window(app) -> MainWindow:
    """Get the main window from the app."""
    return app.main_window


def take_screenshot(root: tk.Tk, filepath: Path) -> bool:
    """Take a screenshot of the tkinter window.

    Args:
        root: The root tkinter window.
        filepath: Path to save the screenshot.

    Returns:
        True if screenshot was taken successfully.
    """
    try:
        from PIL import ImageGrab

        # Update the window to ensure it's rendered
        root.update_idletasks()
        root.update()

        # Get window geometry
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        width = root.winfo_width()
        height = root.winfo_height()

        # Capture the screen region
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        screenshot.save(filepath)
        return True
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return False
