"""Mock data factory for UI development and testing."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass
class PortfolioSummary:
    """Summary metrics for the portfolio."""

    total_value: Decimal
    total_cost_basis: Decimal
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_pct: Decimal
    ytd_harvested_losses: Decimal
    pending_harvest_opportunities: int
    active_wash_sale_restrictions: int


@dataclass
class HarvestOpportunity:
    """A potential harvest opportunity."""

    ticker: str
    name: str
    shares: Decimal
    current_price: Decimal
    cost_basis: Decimal
    unrealized_loss: Decimal
    estimated_tax_benefit: Decimal
    recommended_action: str  # "sell" or "swap"
    swap_target: str | None
    status: str  # "pending", "approved", "rejected", "expired"


@dataclass
class WashSaleRestriction:
    """A wash sale restriction on a ticker."""

    ticker: str
    sale_date: date
    restriction_start: date
    restriction_end: date
    status: str  # "active" or "expired"

    @property
    def days_remaining(self) -> int:
        """Days until the restriction expires."""
        if self.status == "expired":
            return 0
        delta = self.restriction_end - date.today()
        return max(0, delta.days)


@dataclass
class Lot:
    """A tax lot representing a single purchase."""

    shares: Decimal
    cost_per_share: Decimal
    acquired_date: date

    @property
    def total_cost_basis(self) -> Decimal:
        """Total cost basis for this lot."""
        return self.shares * self.cost_per_share


@dataclass
class Position:
    """A portfolio position with associated lots."""

    ticker: str
    name: str
    lots: list[Lot]
    current_price: Decimal
    wash_sale_until: date | None = None

    @property
    def total_shares(self) -> Decimal:
        """Total shares across all lots."""
        return sum((lot.shares for lot in self.lots), Decimal(0))

    @property
    def total_cost_basis(self) -> Decimal:
        """Total cost basis across all lots."""
        return sum((lot.total_cost_basis for lot in self.lots), Decimal(0))

    @property
    def market_value(self) -> Decimal:
        """Current market value."""
        return self.total_shares * self.current_price

    @property
    def unrealized_gain_loss(self) -> Decimal:
        """Unrealized gain/loss."""
        return self.market_value - self.total_cost_basis


@dataclass
class Trade:
    """A trade execution record."""

    ticker: str
    trade_type: str  # "buy" or "sell"
    shares: Decimal
    price_per_share: Decimal
    executed_at: date
    harvest_event_id: str | None = None

    @property
    def total_value(self) -> Decimal:
        """Total value of the trade."""
        return self.shares * self.price_per_share


@dataclass
class LossLedgerEntry:
    """A year's worth of harvested loss tracking."""

    year: int
    short_term_losses: Decimal
    long_term_losses: Decimal
    used_against_gains: Decimal
    carryforward: Decimal


class MockDataFactory:
    """Factory for generating realistic mock data."""

    @staticmethod
    def get_portfolio_summary() -> PortfolioSummary:
        """Get mock portfolio summary data."""
        return PortfolioSummary(
            total_value=Decimal("523847.32"),
            total_cost_basis=Decimal("498234.18"),
            unrealized_gain_loss=Decimal("25613.14"),
            unrealized_gain_loss_pct=Decimal("5.14"),
            ytd_harvested_losses=Decimal("-12456.78"),
            pending_harvest_opportunities=5,
            active_wash_sale_restrictions=3,
        )

    @staticmethod
    def get_harvest_opportunities() -> list[HarvestOpportunity]:
        """Get mock harvest opportunities."""
        return [
            HarvestOpportunity(
                ticker="NVDA",
                name="NVIDIA Corporation",
                shares=Decimal("30"),
                current_price=Decimal("485.00"),
                cost_basis=Decimal("520.00"),
                unrealized_loss=Decimal("-1050.00"),
                estimated_tax_benefit=Decimal("367.50"),
                recommended_action="swap",
                swap_target="XLK",
                status="pending",
            ),
            HarvestOpportunity(
                ticker="AMZN",
                name="Amazon.com Inc.",
                shares=Decimal("15"),
                current_price=Decimal("178.50"),
                cost_basis=Decimal("195.00"),
                unrealized_loss=Decimal("-247.50"),
                estimated_tax_benefit=Decimal("86.63"),
                recommended_action="swap",
                swap_target="XLY",
                status="pending",
            ),
            HarvestOpportunity(
                ticker="GOOGL",
                name="Alphabet Inc.",
                shares=Decimal("20"),
                current_price=Decimal("141.25"),
                cost_basis=Decimal("158.00"),
                unrealized_loss=Decimal("-335.00"),
                estimated_tax_benefit=Decimal("117.25"),
                recommended_action="sell",
                swap_target=None,
                status="pending",
            ),
            HarvestOpportunity(
                ticker="META",
                name="Meta Platforms Inc.",
                shares=Decimal("12"),
                current_price=Decimal("505.00"),
                cost_basis=Decimal("540.00"),
                unrealized_loss=Decimal("-420.00"),
                estimated_tax_benefit=Decimal("147.00"),
                recommended_action="swap",
                swap_target="XLC",
                status="pending",
            ),
            HarvestOpportunity(
                ticker="TSLA",
                name="Tesla Inc.",
                shares=Decimal("25"),
                current_price=Decimal("248.50"),
                cost_basis=Decimal("275.00"),
                unrealized_loss=Decimal("-662.50"),
                estimated_tax_benefit=Decimal("231.88"),
                recommended_action="swap",
                swap_target="XLY",
                status="pending",
            ),
        ]

    @staticmethod
    def get_active_wash_sale_restrictions() -> list[WashSaleRestriction]:
        """Get mock active wash sale restrictions."""
        today = date.today()
        return [
            WashSaleRestriction(
                ticker="MSFT",
                sale_date=today - timedelta(days=18),
                restriction_start=today - timedelta(days=48),
                restriction_end=today + timedelta(days=12),
                status="active",
            ),
            WashSaleRestriction(
                ticker="AAPL",
                sale_date=today - timedelta(days=7),
                restriction_start=today - timedelta(days=37),
                restriction_end=today + timedelta(days=23),
                status="active",
            ),
            WashSaleRestriction(
                ticker="VTI",
                sale_date=today - timedelta(days=35),
                restriction_start=today - timedelta(days=65),
                restriction_end=today - timedelta(days=5),
                status="expired",
            ),
        ]

    @staticmethod
    def get_positions() -> list[Position]:
        """Get mock portfolio positions."""
        return [
            Position(
                ticker="AAPL",
                name="Apple Inc.",
                lots=[
                    Lot(Decimal("25"), Decimal("142.50"), date(2023, 3, 15)),
                    Lot(Decimal("25"), Decimal("158.20"), date(2023, 8, 22)),
                ],
                current_price=Decimal("195.50"),
            ),
            Position(
                ticker="MSFT",
                name="Microsoft Corporation",
                lots=[
                    Lot(Decimal("40"), Decimal("285.00"), date(2023, 5, 10)),
                ],
                current_price=Decimal("378.50"),
                wash_sale_until=date.today() + timedelta(days=12),
            ),
            Position(
                ticker="NVDA",
                name="NVIDIA Corporation",
                lots=[
                    Lot(Decimal("30"), Decimal("520.00"), date(2024, 1, 10)),
                ],
                current_price=Decimal("485.00"),
            ),
            Position(
                ticker="GOOGL",
                name="Alphabet Inc.",
                lots=[
                    Lot(Decimal("20"), Decimal("158.00"), date(2024, 2, 5)),
                ],
                current_price=Decimal("141.25"),
            ),
            Position(
                ticker="AMZN",
                name="Amazon.com Inc.",
                lots=[
                    Lot(Decimal("15"), Decimal("195.00"), date(2024, 3, 1)),
                ],
                current_price=Decimal("178.50"),
            ),
            Position(
                ticker="META",
                name="Meta Platforms Inc.",
                lots=[
                    Lot(Decimal("12"), Decimal("540.00"), date(2024, 1, 20)),
                ],
                current_price=Decimal("505.00"),
            ),
            Position(
                ticker="TSLA",
                name="Tesla Inc.",
                lots=[
                    Lot(Decimal("25"), Decimal("275.00"), date(2024, 2, 15)),
                ],
                current_price=Decimal("248.50"),
            ),
            Position(
                ticker="VTI",
                name="Vanguard Total Stock Market ETF",
                lots=[
                    Lot(Decimal("100"), Decimal("210.00"), date(2022, 6, 1)),
                    Lot(Decimal("50"), Decimal("225.00"), date(2023, 1, 15)),
                ],
                current_price=Decimal("262.50"),
            ),
            Position(
                ticker="VOO",
                name="Vanguard S&P 500 ETF",
                lots=[
                    Lot(Decimal("75"), Decimal("380.00"), date(2022, 9, 1)),
                ],
                current_price=Decimal("478.25"),
            ),
            Position(
                ticker="BRK.B",
                name="Berkshire Hathaway Inc.",
                lots=[
                    Lot(Decimal("30"), Decimal("310.00"), date(2023, 4, 1)),
                ],
                current_price=Decimal("412.50"),
            ),
        ]

    @staticmethod
    def get_trade_history() -> list[Trade]:
        """Get mock trade history."""
        today = date.today()
        return [
            Trade(
                ticker="NVDA",
                trade_type="sell",
                shares=Decimal("30"),
                price_per_share=Decimal("485.00"),
                executed_at=today - timedelta(days=1),
                harvest_event_id="h001",
            ),
            Trade(
                ticker="XLK",
                trade_type="buy",
                shares=Decimal("85"),
                price_per_share=Decimal("170.50"),
                executed_at=today - timedelta(days=1),
                harvest_event_id="h001",
            ),
            Trade(
                ticker="AAPL",
                trade_type="sell",
                shares=Decimal("25"),
                price_per_share=Decimal("192.30"),
                executed_at=today - timedelta(days=7),
                harvest_event_id="h002",
            ),
            Trade(
                ticker="MSFT",
                trade_type="sell",
                shares=Decimal("40"),
                price_per_share=Decimal("375.20"),
                executed_at=today - timedelta(days=18),
                harvest_event_id="h003",
            ),
            Trade(
                ticker="XLK",
                trade_type="buy",
                shares=Decimal("88"),
                price_per_share=Decimal("168.75"),
                executed_at=today - timedelta(days=18),
                harvest_event_id="h003",
            ),
        ]

    @staticmethod
    def get_loss_ledger() -> list[LossLedgerEntry]:
        """Get mock loss ledger entries."""
        return [
            LossLedgerEntry(
                year=2024,
                short_term_losses=Decimal("-12456.78"),
                long_term_losses=Decimal("-3200.00"),
                used_against_gains=Decimal("7422.22"),
                carryforward=Decimal("8234.56"),
            ),
            LossLedgerEntry(
                year=2023,
                short_term_losses=Decimal("-8900.00"),
                long_term_losses=Decimal("-2100.00"),
                used_against_gains=Decimal("11000.00"),
                carryforward=Decimal("0.00"),
            ),
            LossLedgerEntry(
                year=2022,
                short_term_losses=Decimal("-15234.00"),
                long_term_losses=Decimal("-4500.00"),
                used_against_gains=Decimal("19734.00"),
                carryforward=Decimal("0.00"),
            ),
        ]
