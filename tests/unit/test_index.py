"""Tests for S&P 500 index tracking service."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_parse_wikipedia_table(self, service: IndexService) -> None:
        """Test parsing S&P 500 table from Wikipedia HTML."""
        html = """
        <html>
        <table class="wikitable">
            <tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr>
            <tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td></tr>
            <tr><td>MSFT</td><td>Microsoft Corporation</td><td>Information Technology</td></tr>
            <tr><td>GOOGL</td><td>Alphabet Inc.</td><td>Communication Services</td></tr>
        </table>
        </html>
        """

        constituents = service._parse_wikipedia_table(html)

        assert len(constituents) == 3
        assert constituents[0].symbol == "AAPL"
        assert constituents[0].name == "Apple Inc."
        assert constituents[0].sector == "Information Technology"
        # Equal weights: 100 / 3 = 33.3333...
        assert constituents[0].weight == Decimal("33.3333")

    def test_parse_wikipedia_table_empty(self, service: IndexService) -> None:
        """Test parsing empty HTML."""
        html = "<html><body></body></html>"

        constituents = service._parse_wikipedia_table(html)

        assert constituents == []

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


class TestIndexServiceAsync:
    """Async tests for IndexService."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> IndexService:
        """Create an IndexService instance."""
        return IndexService(cache_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_fetch_sp500_constituents(self, service: IndexService) -> None:
        """Test fetching S&P 500 constituents."""
        mock_html = """
        <html>
        <table class="wikitable">
            <tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr>
            <tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td></tr>
        </table>
        </html>
        """

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.text = AsyncMock(return_value=mock_html)

            mock_session = MagicMock()
            mock_get_cm = AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(),
            )
            mock_session.get = MagicMock(return_value=mock_get_cm)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_session_class.return_value = mock_session

            constituents = await service.fetch_sp500_constituents()

            assert len(constituents) == 1
            assert constituents[0].symbol == "AAPL"
