"""Index tracking service for direct indexing.

Provides index constituent data and target allocation calculations
for index-tracking investment strategies.

Supported indexes:
- S&P 500 (500 large-cap stocks)
- Nasdaq 100 (100 large-cap tech-heavy)
- Dow Jones (30 blue-chip stocks)
- Russell 1000 (1000 large-cap)
- Russell 2000 (2000 small-cap)
- Russell 3000 (3000 total market)

Data sources: ETF holdings files from fund providers.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class IndexType(Enum):
    """Supported market indexes for direct indexing."""

    SP500 = "sp500"           # S&P 500 - 500 large-cap
    NASDAQ100 = "nasdaq100"   # Nasdaq 100 - 100 tech-heavy
    DOWJONES = "dowjones"     # Dow Jones Industrial Average - 30 blue-chip
    RUSSELL1000 = "russell1000"  # Russell 1000 - 1000 large-cap
    RUSSELL2000 = "russell2000"  # Russell 2000 - 2000 small-cap
    RUSSELL3000 = "russell3000"  # Russell 3000 - total market


# ETF holdings URLs for each index
INDEX_ETF_URLS = {
    IndexType.SP500: {
        "etf": "SPY",
        "provider": "State Street",
        "url": (
            "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
            "holdings-daily-us-en-spy.xlsx"
        ),
    },
    IndexType.NASDAQ100: {
        "etf": "QQQ",
        "provider": "Invesco",
        "url": (
            "https://www.invesco.com/us/financial-products/etfs/holdings/main/"
            "holdings/0?audienceType=Investor&action=download&ticker=QQQ"
        ),
    },
    IndexType.DOWJONES: {
        "etf": "DIA",
        "provider": "State Street",
        "url": (
            "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
            "holdings-daily-us-en-dia.xlsx"
        ),
    },
    IndexType.RUSSELL1000: {
        "etf": "IWB",
        "provider": "iShares",
        "url": (
            "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"
        ),
    },
    IndexType.RUSSELL2000: {
        "etf": "IWM",
        "provider": "iShares",
        "url": (
            "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
        ),
    },
    IndexType.RUSSELL3000: {
        "etf": "IWV",
        "provider": "iShares",
        "url": (
            "https://www.ishares.com/us/products/239714/ishares-russell-3000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWV_holdings&dataType=fund"
        ),
    },
}


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

    Fetches S&P 500 constituent data with market-cap weights from:
    1. SPY ETF holdings (State Street) - primary source with exact weights
    2. Slickcharts - fallback with approximate weights
    """

    # SPY ETF holdings from State Street (exact weights)
    SPY_XLSX_URL = (
        "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
        "holdings-daily-us-en-spy.xlsx"
    )

    # Slickcharts fallback (approximate weights)
    SLICKCHARTS_URL = "https://www.slickcharts.com/sp500"

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

    def fetch_sp500_weights(self) -> list[IndexConstituent]:
        """Fetch S&P 500 constituents with market-cap weights.

        Tries SPY ETF holdings first (exact weights), falls back to Slickcharts.

        Returns:
            List of index constituents with weights.
        """
        # Try SPY XLSX first (best source - exact weights)
        try:
            return self._fetch_from_spy_xlsx()
        except Exception as e:
            logger.warning(f"SPY XLSX failed, falling back to Slickcharts: {e}")

        # Fallback to Slickcharts
        try:
            return self._fetch_from_slickcharts()
        except Exception as e:
            logger.error(f"Slickcharts also failed: {e}")
            raise RuntimeError("Failed to fetch S&P 500 data from any source") from e

    def _fetch_from_spy_xlsx(self) -> list[IndexConstituent]:
        """Fetch weights from SPY ETF holdings XLSX.

        Returns:
            List of constituents with exact weights.
        """
        df = pd.read_excel(
            self.SPY_XLSX_URL,
            engine="openpyxl",
            skiprows=4,  # Skip header junk
        )

        # Normalize column names
        df.columns = [str(c).strip() for c in df.columns]

        # Find the relevant columns (names may vary slightly)
        ticker_col = None
        name_col = None
        weight_col = None
        sector_col = None

        for col in df.columns:
            col_lower = col.lower()
            if "ticker" in col_lower or "symbol" in col_lower:
                ticker_col = col
            elif "name" in col_lower and "security" not in col_lower:
                name_col = col
            elif "weight" in col_lower:
                weight_col = col
            elif "sector" in col_lower:
                sector_col = col

        if not ticker_col or not weight_col:
            raise ValueError(f"Could not find required columns. Found: {list(df.columns)}")

        # Use ticker as name if no name column
        if not name_col:
            name_col = ticker_col

        constituents = []
        for _, row in df.iterrows():
            ticker = str(row[ticker_col]).strip()
            if not ticker or ticker == "nan" or len(ticker) > 5:
                continue  # Skip invalid rows

            weight = row[weight_col]
            if pd.isna(weight):
                continue

            # Convert weight to percentage if needed
            weight_pct = float(weight)
            if weight_pct < 1:  # Appears to be a fraction (0.07 instead of 7%)
                weight_pct *= 100

            name = str(row[name_col]).strip() if name_col else ticker
            sector_val = row.get(sector_col) if sector_col else None
            has_sector = sector_val and not pd.isna(sector_val)
            sector = str(sector_val).strip() if has_sector else "Unknown"

            constituents.append(
                IndexConstituent(
                    symbol=ticker,
                    name=name if name != "nan" else ticker,
                    weight=Decimal(str(weight_pct)).quantize(Decimal("0.0001")),
                    sector=sector if sector != "nan" else "Unknown",
                )
            )

        if not constituents:
            raise ValueError("No valid constituents found in SPY XLSX")

        logger.info(f"Loaded {len(constituents)} constituents from SPY XLSX")
        return constituents

    def _fetch_from_slickcharts(self) -> list[IndexConstituent]:
        """Fetch weights from Slickcharts (fallback).

        Returns:
            List of constituents with approximate weights.
        """
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(self.SLICKCHARTS_URL, headers=headers, timeout=10)
        resp.raise_for_status()

        # Parse HTML tables with pandas
        tables = pd.read_html(resp.text)
        if not tables:
            raise ValueError("No tables found on Slickcharts page")

        df = tables[0]

        # Slickcharts columns: ['#', 'Company', 'Symbol', 'Weight', 'Price', ...]
        constituents = []
        for _, row in df.iterrows():
            symbol = str(row.get("Symbol", "")).strip()
            if not symbol or symbol == "nan":
                continue

            weight_str = str(row.get("Weight", "0"))
            weight_pct = float(weight_str.rstrip("%"))

            name = str(row.get("Company", symbol)).strip()

            constituents.append(
                IndexConstituent(
                    symbol=symbol,
                    name=name if name != "nan" else symbol,
                    weight=Decimal(str(weight_pct)).quantize(Decimal("0.0001")),
                    sector="Unknown",  # Slickcharts doesn't provide sector
                )
            )

        if not constituents:
            raise ValueError("No valid constituents found on Slickcharts")

        logger.info(f"Loaded {len(constituents)} constituents from Slickcharts")
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

    def get_constituents(self) -> list[IndexConstituent]:
        """Get S&P 500 constituents, using cache if available.

        Returns:
            List of index constituents with market-cap weights.
        """
        # Try cache first
        cached = self.get_cached_constituents()
        if cached:
            return cached

        # Fetch fresh data
        constituents = self.fetch_sp500_weights()

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

    def get_top_holdings(
        self,
        n: int = 10,
        constituents: list[IndexConstituent] | None = None,
    ) -> list[IndexConstituent]:
        """Get the top N holdings by weight.

        Args:
            n: Number of top holdings to return.
            constituents: Optional list of constituents.

        Returns:
            List of top N constituents by weight.
        """
        if constituents is None:
            constituents = self._constituents or []

        sorted_constituents = sorted(constituents, key=lambda c: c.weight, reverse=True)
        return sorted_constituents[:n]
