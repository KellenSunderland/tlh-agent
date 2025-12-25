"""S&P 500 index tracking service.

Provides S&P 500 constituent data and target allocation calculations
for index-tracking investment strategies.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup


@dataclass
class IndexConstituent:
    """A constituent of the S&P 500 index."""

    symbol: str
    name: str
    weight: Decimal  # Market cap weight as percentage (e.g., 7.0 for 7%)
    sector: str


@dataclass
class TargetAllocation:
    """Target allocation for a position to track the index."""

    symbol: str
    name: str
    target_weight: Decimal  # Target weight as percentage
    target_value: Decimal  # Target value in dollars
    current_value: Decimal  # Current value in dollars
    difference: Decimal  # Amount to buy (positive) or sell (negative)
    difference_pct: Decimal  # Difference as percentage of target


@dataclass
class Position:
    """A portfolio position (simplified for allocation calculations)."""

    symbol: str
    market_value: Decimal


class IndexService:
    """Service for S&P 500 index tracking.

    Fetches S&P 500 constituent data from Wikipedia and calculates
    target allocations for index-tracking portfolios.
    """

    # Wikipedia URL for S&P 500 list
    SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # Cache expiry time (24 hours)
    CACHE_EXPIRY_HOURS = 24

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the index service.

        Args:
            cache_dir: Directory to cache constituent data.
        """
        self._cache_dir = cache_dir or Path.home() / ".tlh-agent"
        self._cache_file = self._cache_dir / "sp500_constituents.json"
        self._constituents: list[IndexConstituent] | None = None
        self._last_fetch: datetime | None = None

    async def fetch_sp500_constituents(self) -> list[IndexConstituent]:
        """Fetch S&P 500 constituents from Wikipedia.

        Returns:
            List of index constituents with weights.
        """
        async with (
            aiohttp.ClientSession() as session,
            session.get(self.SP500_URL) as response,
        ):
            response.raise_for_status()
            html = await response.text()

        return self._parse_wikipedia_table(html)

    def _parse_wikipedia_table(self, html: str) -> list[IndexConstituent]:
        """Parse S&P 500 table from Wikipedia HTML.

        Args:
            html: Raw HTML from Wikipedia.

        Returns:
            List of constituents parsed from the table.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Find the main table (first table with "Symbol" header)
        constituents = []
        tables = soup.find_all("table", class_="wikitable")

        for table in tables:
            headers = table.find_all("th")
            header_text = [h.get_text(strip=True).lower() for h in headers]

            if "symbol" in header_text:
                # Found the right table
                symbol_idx = header_text.index("symbol")
                name_idx = header_text.index("security") if "security" in header_text else -1
                sector_idx = (
                    header_text.index("gics sector") if "gics sector" in header_text else -1
                )

                rows = table.find_all("tr")[1:]  # Skip header row

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) > symbol_idx:
                        symbol = cells[symbol_idx].get_text(strip=True)
                        name = cells[name_idx].get_text(strip=True) if name_idx >= 0 else symbol
                        sector = (
                            cells[sector_idx].get_text(strip=True)
                            if sector_idx >= 0 and len(cells) > sector_idx
                            else "Unknown"
                        )

                        # Wikipedia doesn't have weights, we'll use equal weight
                        # for now. Real implementation would fetch from financial API
                        constituents.append(
                            IndexConstituent(
                                symbol=symbol,
                                name=name,
                                weight=Decimal("0"),  # Will be calculated below
                                sector=sector,
                            )
                        )

                break

        # Calculate equal weights if no weights provided
        if constituents:
            equal_weight = Decimal("100") / len(constituents)
            for c in constituents:
                c.weight = equal_weight.quantize(Decimal("0.0001"))

        return constituents

    def get_cached_constituents(self) -> list[IndexConstituent] | None:
        """Get cached constituents if available and not expired.

        Returns:
            List of constituents if cache is valid, None otherwise.
        """
        cache_is_valid = (
            self._constituents
            and self._last_fetch
            and datetime.now() - self._last_fetch < timedelta(hours=self.CACHE_EXPIRY_HOURS)
        )
        if cache_is_valid:
            return self._constituents

        # Try to load from file cache
        if self._cache_file.exists():
            try:
                import json

                data = json.loads(self._cache_file.read_text())
                last_fetch = datetime.fromisoformat(data["last_fetch"])

                if datetime.now() - last_fetch < timedelta(hours=self.CACHE_EXPIRY_HOURS):
                    self._constituents = [
                        IndexConstituent(
                            symbol=c["symbol"],
                            name=c["name"],
                            weight=Decimal(c["weight"]),
                            sector=c["sector"],
                        )
                        for c in data["constituents"]
                    ]
                    self._last_fetch = last_fetch
                    return self._constituents
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        return None

    def save_cache(self, constituents: list[IndexConstituent]) -> None:
        """Save constituents to cache file.

        Args:
            constituents: List of constituents to cache.
        """
        import json

        self._cache_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "last_fetch": datetime.now().isoformat(),
            "constituents": [
                {
                    "symbol": c.symbol,
                    "name": c.name,
                    "weight": str(c.weight),
                    "sector": c.sector,
                }
                for c in constituents
            ],
        }

        self._cache_file.write_text(json.dumps(data, indent=2))
        self._constituents = constituents
        self._last_fetch = datetime.now()

    async def get_constituents(self) -> list[IndexConstituent]:
        """Get S&P 500 constituents, using cache if available.

        Returns:
            List of index constituents.
        """
        # Try cache first
        cached = self.get_cached_constituents()
        if cached:
            return cached

        # Fetch fresh data
        constituents = await self.fetch_sp500_constituents()

        # Save to cache
        self.save_cache(constituents)

        return constituents

    def calculate_target_allocations(
        self,
        portfolio_value: Decimal,
        current_positions: list[Position],
        constituents: list[IndexConstituent] | None = None,
    ) -> list[TargetAllocation]:
        """Calculate target allocations to track the S&P 500.

        Args:
            portfolio_value: Total portfolio value to allocate.
            current_positions: List of current positions.
            constituents: Optional list of constituents (uses cached if not provided).

        Returns:
            List of target allocations with differences from current positions.
        """
        if constituents is None:
            constituents = self._constituents or []

        # Build lookup of current positions
        current_by_symbol = {p.symbol: p.market_value for p in current_positions}

        allocations = []
        for constituent in constituents:
            # Calculate target value based on weight
            target_value = (portfolio_value * constituent.weight / 100).quantize(Decimal("0.01"))

            # Get current value (0 if not held)
            current_value = current_by_symbol.get(constituent.symbol, Decimal("0"))

            # Calculate difference
            difference = target_value - current_value

            # Calculate difference as percentage of target
            diff_pct = Decimal("0")
            if target_value > 0:
                diff_pct = ((difference / target_value) * 100).quantize(Decimal("0.01"))

            allocations.append(
                TargetAllocation(
                    symbol=constituent.symbol,
                    name=constituent.name,
                    target_weight=constituent.weight,
                    target_value=target_value,
                    current_value=current_value,
                    difference=difference,
                    difference_pct=diff_pct,
                )
            )

        # Sort by absolute difference (largest gaps first)
        allocations.sort(key=lambda a: abs(a.difference), reverse=True)

        return allocations

    def get_rebalance_trades(
        self,
        portfolio_value: Decimal,
        current_positions: list[Position],
        threshold_pct: Decimal = Decimal("1.0"),
        constituents: list[IndexConstituent] | None = None,
    ) -> list[TargetAllocation]:
        """Get list of trades needed to rebalance to target allocations.

        Only returns allocations where the difference exceeds the threshold.

        Args:
            portfolio_value: Total portfolio value.
            current_positions: List of current positions.
            threshold_pct: Minimum difference percentage to trigger rebalance.
            constituents: Optional list of constituents.

        Returns:
            List of allocations that need rebalancing.
        """
        all_allocations = self.calculate_target_allocations(
            portfolio_value, current_positions, constituents
        )

        # Filter to only those exceeding threshold
        return [a for a in all_allocations if abs(a.difference_pct) >= threshold_pct]

    def get_sector_summary(
        self, constituents: list[IndexConstituent] | None = None
    ) -> dict[str, Decimal]:
        """Get summary of weights by sector.

        Args:
            constituents: Optional list of constituents.

        Returns:
            Dictionary mapping sector names to total weights.
        """
        if constituents is None:
            constituents = self._constituents or []

        sector_weights: dict[str, Decimal] = {}
        for c in constituents:
            if c.sector in sector_weights:
                sector_weights[c.sector] += c.weight
            else:
                sector_weights[c.sector] = c.weight

        return sector_weights
