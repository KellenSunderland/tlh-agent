"""Tests for S&P 500 index tracking service."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tlh_agent.services.index import IndexConstituent, IndexService, Position, TargetAllocation


class TestIndexConstituent:
    """Tests for IndexConstituent dataclass."""

    def test_create_constituent(self) -> None:
        """Test creating an index constituent."""
        constituent = IndexConstituent(
            symbol="AAPL",
            name="Apple Inc.",
            weight=Decimal("7.0"),
            sector="Information Technology",
        )

        assert constituent.symbol == "AAPL"
        assert constituent.name == "Apple Inc."
        assert constituent.weight == Decimal("7.0")
        assert constituent.sector == "Information Technology"


class TestTargetAllocation:
    """Tests for TargetAllocation dataclass."""

    def test_create_allocation(self) -> None:
        """Test creating a target allocation."""
        allocation = TargetAllocation(
            symbol="AAPL",
            name="Apple Inc.",
            target_weight=Decimal("7.0"),
            target_value=Decimal("7000.00"),
            current_value=Decimal("5000.00"),
            difference=Decimal("2000.00"),
            difference_pct=Decimal("28.57"),
        )

        assert allocation.symbol == "AAPL"
        assert allocation.target_value == Decimal("7000.00")
        assert allocation.difference == Decimal("2000.00")


class TestIndexService:
    """Tests for IndexService."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        cache_dir = tmp_path / ".tlh-agent"
        cache_dir.mkdir(parents=True)
        return cache_dir

    @pytest.fixture
    def service(self, temp_cache_dir: Path) -> IndexService:
        """Create an IndexService instance."""
        return IndexService(cache_dir=temp_cache_dir)

    def test_init_default_cache_dir(self) -> None:
        """Test initialization with default cache directory."""
        service = IndexService()

        assert service._cache_dir == Path.home() / ".tlh-agent"

    def test_init_custom_cache_dir(self, temp_cache_dir: Path) -> None:
        """Test initialization with custom cache directory."""
        service = IndexService(cache_dir=temp_cache_dir)

        assert service._cache_dir == temp_cache_dir

    def test_get_cached_constituents_empty(self, service: IndexService) -> None:
        """Test getting cached constituents when cache is empty."""
        result = service.get_cached_constituents()

        assert result is None

    def test_get_cached_constituents_memory_cache(self, service: IndexService) -> None:
        """Test getting cached constituents from memory."""
        service._constituents = [
            IndexConstituent(
                symbol="AAPL",
                name="Apple Inc.",
                weight=Decimal("7.0"),
                sector="Technology",
            )
        ]
        service._last_fetch = datetime.now()

        result = service.get_cached_constituents()

        assert result is not None
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_get_cached_constituents_expired(self, service: IndexService) -> None:
        """Test that expired cache returns None."""
        service._constituents = [
            IndexConstituent(
                symbol="AAPL",
                name="Apple Inc.",
                weight=Decimal("7.0"),
                sector="Technology",
            )
        ]
        # Set last fetch to 25 hours ago (expired)
        service._last_fetch = datetime.now() - timedelta(hours=25)

        result = service.get_cached_constituents()

        assert result is None

    def test_save_cache(self, service: IndexService, temp_cache_dir: Path) -> None:
        """Test saving constituents to cache."""
        constituents = [
            IndexConstituent(
                symbol="AAPL",
                name="Apple Inc.",
                weight=Decimal("7.0"),
                sector="Technology",
            ),
            IndexConstituent(
                symbol="MSFT",
                name="Microsoft",
                weight=Decimal("6.5"),
                sector="Technology",
            ),
        ]

        service.save_cache(constituents)

        # Check file was created
        cache_file = temp_cache_dir / "sp500_constituents.json"
        assert cache_file.exists()

        # Check data
        data = json.loads(cache_file.read_text())
        assert len(data["constituents"]) == 2
        assert data["constituents"][0]["symbol"] == "AAPL"

        # Check memory cache
        assert service._constituents == constituents
        assert service._last_fetch is not None

    def test_get_cached_constituents_from_file(
        self, service: IndexService, temp_cache_dir: Path
    ) -> None:
        """Test loading cached constituents from file."""
        # Write cache file
        cache_file = temp_cache_dir / "sp500_constituents.json"
        cache_data = {
            "last_fetch": datetime.now().isoformat(),
            "constituents": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "weight": "7.0",
                    "sector": "Technology",
                }
            ],
        }
        cache_file.write_text(json.dumps(cache_data))

        result = service.get_cached_constituents()

        assert result is not None
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_calculate_target_allocations(self, service: IndexService) -> None:
        """Test calculating target allocations."""
        service._constituents = [
            IndexConstituent(symbol="AAPL", name="Apple", weight=Decimal("50"), sector="Tech"),
            IndexConstituent(symbol="MSFT", name="Microsoft", weight=Decimal("50"), sector="Tech"),
        ]

        current_positions = [
            Position(symbol="AAPL", market_value=Decimal("4000")),
            # MSFT not held
        ]

        allocations = service.calculate_target_allocations(
            portfolio_value=Decimal("10000"),
            current_positions=current_positions,
        )

        assert len(allocations) == 2

        # Find AAPL allocation
        aapl = next(a for a in allocations if a.symbol == "AAPL")
        assert aapl.target_value == Decimal("5000.00")
        assert aapl.current_value == Decimal("4000")
        assert aapl.difference == Decimal("1000.00")

        # Find MSFT allocation
        msft = next(a for a in allocations if a.symbol == "MSFT")
        assert msft.target_value == Decimal("5000.00")
        assert msft.current_value == Decimal("0")
        assert msft.difference == Decimal("5000.00")

    def test_get_rebalance_trades_filters_by_threshold(self, service: IndexService) -> None:
        """Test that rebalance trades are filtered by threshold."""
        service._constituents = [
            IndexConstituent(symbol="AAPL", name="Apple", weight=Decimal("50"), sector="Tech"),
            IndexConstituent(symbol="MSFT", name="Microsoft", weight=Decimal("50"), sector="Tech"),
        ]

        current_positions = [
            Position(symbol="AAPL", market_value=Decimal("4950")),  # Only 1% off
            Position(symbol="MSFT", market_value=Decimal("4000")),  # 20% off
        ]

        trades = service.get_rebalance_trades(
            portfolio_value=Decimal("10000"),
            current_positions=current_positions,
            threshold_pct=Decimal("5.0"),  # 5% threshold
        )

        # Only MSFT should be returned (20% off > 5% threshold)
        assert len(trades) == 1
        assert trades[0].symbol == "MSFT"

    def test_get_sector_summary(self, service: IndexService) -> None:
        """Test getting sector summary."""
        service._constituents = [
            IndexConstituent(
                symbol="AAPL", name="Apple", weight=Decimal("7.0"), sector="Technology"
            ),
            IndexConstituent(
                symbol="MSFT", name="Microsoft", weight=Decimal("6.5"), sector="Technology"
            ),
            IndexConstituent(
                symbol="JPM", name="JPMorgan", weight=Decimal("2.0"), sector="Financials"
            ),
        ]

        summary = service.get_sector_summary()

        assert summary["Technology"] == Decimal("13.5")
        assert summary["Financials"] == Decimal("2.0")

    def test_get_sector_summary_empty(self, service: IndexService) -> None:
        """Test getting sector summary with no constituents."""
        service._constituents = []

        summary = service.get_sector_summary()

        assert summary == {}

    def test_get_top_holdings(self, service: IndexService) -> None:
        """Test getting top holdings by weight."""
        service._constituents = [
            IndexConstituent(symbol="AAPL", name="Apple", weight=Decimal("7.0"), sector="Tech"),
            IndexConstituent(symbol="MSFT", name="Microsoft", weight=Decimal("6.5"), sector="Tech"),
            IndexConstituent(symbol="NVDA", name="NVIDIA", weight=Decimal("6.0"), sector="Tech"),
            IndexConstituent(symbol="AMZN", name="Amazon", weight=Decimal("3.5"), sector="Tech"),
            IndexConstituent(symbol="GOOGL", name="Alphabet", weight=Decimal("2.0"), sector="Tech"),
        ]

        top_3 = service.get_top_holdings(n=3)

        assert len(top_3) == 3
        assert top_3[0].symbol == "AAPL"
        assert top_3[1].symbol == "MSFT"
        assert top_3[2].symbol == "NVDA"


class TestIndexServiceFetch:
    """Tests for IndexService fetching methods."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> IndexService:
        """Create an IndexService instance."""
        return IndexService(cache_dir=tmp_path)

    def test_fetch_from_spy_xlsx(self, service: IndexService) -> None:
        """Test fetching from SPY XLSX with mocked pandas."""
        sectors = ["Information Technology"] * 3
        mock_df = pd.DataFrame({
            "Ticker": ["AAPL", "MSFT", "NVDA"],
            "Name": ["Apple Inc.", "Microsoft Corp", "NVIDIA Corp"],
            "Weight": [0.07, 0.065, 0.06],  # Fractions
            "Sector": sectors,
        })

        with patch("pandas.read_excel", return_value=mock_df):
            constituents = service._fetch_from_spy_xlsx()

        assert len(constituents) == 3
        assert constituents[0].symbol == "AAPL"
        assert constituents[0].name == "Apple Inc."
        assert constituents[0].weight == Decimal("7.0000")  # Converted from 0.07
        assert constituents[0].sector == "Information Technology"

    def test_fetch_from_spy_xlsx_percentage_weights(self, service: IndexService) -> None:
        """Test fetching when weights are already percentages."""
        mock_df = pd.DataFrame({
            "Ticker": ["AAPL", "MSFT"],
            "Name": ["Apple Inc.", "Microsoft Corp"],
            "Weight": [7.0, 6.5],  # Already percentages
            "Sector": ["Technology", "Technology"],
        })

        with patch("pandas.read_excel", return_value=mock_df):
            constituents = service._fetch_from_spy_xlsx()

        assert constituents[0].weight == Decimal("7.0000")
        assert constituents[1].weight == Decimal("6.5000")

    def test_fetch_from_slickcharts(self, service: IndexService) -> None:
        """Test fetching from Slickcharts fallback."""
        mock_df = pd.DataFrame({
            "Company": ["Apple Inc.", "Microsoft Corp", "NVIDIA Corp"],
            "Symbol": ["AAPL", "MSFT", "NVDA"],
            "Weight": ["7.0%", "6.5%", "6.0%"],
        })

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "<html><table></table></html>"

        with (
            patch("requests.get", return_value=mock_response),
            patch("pandas.read_html", return_value=[mock_df]),
        ):
            constituents = service._fetch_from_slickcharts()

        assert len(constituents) == 3
        assert constituents[0].symbol == "AAPL"
        assert constituents[0].name == "Apple Inc."
        assert constituents[0].weight == Decimal("7.0000")
        assert constituents[0].sector == "Unknown"  # Slickcharts doesn't provide sector

    def test_fetch_sp500_weights_primary_source(self, service: IndexService) -> None:
        """Test fetching weights tries SPY XLSX first."""
        mock_df = pd.DataFrame({
            "Ticker": ["AAPL"],
            "Name": ["Apple Inc."],
            "Weight": [7.0],
            "Sector": ["Technology"],
        })

        with patch("pandas.read_excel", return_value=mock_df):
            constituents = service.fetch_sp500_weights()

        assert len(constituents) == 1
        assert constituents[0].symbol == "AAPL"

    def test_fetch_sp500_weights_fallback_to_slickcharts(self, service: IndexService) -> None:
        """Test fetching weights falls back to Slickcharts on SPY failure."""
        mock_slickcharts_df = pd.DataFrame({
            "Company": ["Apple Inc."],
            "Symbol": ["AAPL"],
            "Weight": ["7.0%"],
        })

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "<html><table></table></html>"

        with (
            patch("pandas.read_excel", side_effect=Exception("Network error")),
            patch("requests.get", return_value=mock_response),
            patch("pandas.read_html", return_value=[mock_slickcharts_df]),
        ):
            constituents = service.fetch_sp500_weights()

        assert len(constituents) == 1
        assert constituents[0].symbol == "AAPL"

    def test_fetch_sp500_weights_all_sources_fail(self, service: IndexService) -> None:
        """Test that error is raised when all sources fail."""
        with (
            patch("pandas.read_excel", side_effect=Exception("SPY failed")),
            patch("requests.get", side_effect=Exception("Slickcharts failed")),
            pytest.raises(RuntimeError, match="Failed to fetch S&P 500 data"),
        ):
            service.fetch_sp500_weights()

    def test_get_constituents_uses_cache(self, service: IndexService) -> None:
        """Test that get_constituents uses cache when available."""
        service._constituents = [
            IndexConstituent(symbol="AAPL", name="Apple", weight=Decimal("7.0"), sector="Tech")
        ]
        service._last_fetch = datetime.now()

        with patch("pandas.read_excel") as mock_excel:
            constituents = service.get_constituents()

        # Should not have called read_excel since cache is valid
        mock_excel.assert_not_called()
        assert len(constituents) == 1
        assert constituents[0].symbol == "AAPL"

    def test_get_constituents_fetches_when_cache_expired(self, service: IndexService) -> None:
        """Test that get_constituents fetches fresh data when cache is expired."""
        service._constituents = [
            IndexConstituent(symbol="OLD", name="Old", weight=Decimal("1.0"), sector="Tech")
        ]
        service._last_fetch = datetime.now() - timedelta(hours=25)

        mock_df = pd.DataFrame({
            "Ticker": ["NEW"],
            "Name": ["New Stock"],
            "Weight": [5.0],
            "Sector": ["Technology"],
        })

        with patch("pandas.read_excel", return_value=mock_df):
            constituents = service.get_constituents()

        assert len(constituents) == 1
        assert constituents[0].symbol == "NEW"
