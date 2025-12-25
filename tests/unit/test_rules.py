"""Tests for harvest rules service."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from tlh_agent.brokers.alpaca import AlpacaOrder, AlpacaPosition
from tlh_agent.services.rules import HarvestEvaluator, HarvestRules


@pytest.fixture
def default_rules() -> HarvestRules:
    """Create default harvest rules."""
    return HarvestRules()


@pytest.fixture
def evaluator(default_rules: HarvestRules) -> HarvestEvaluator:
    """Create evaluator with default rules."""
    return HarvestEvaluator(default_rules)


def make_position(
    symbol: str = "AAPL",
    qty: Decimal = Decimal("100"),
    avg_entry_price: Decimal = Decimal("150.00"),
    current_price: Decimal = Decimal("140.00"),
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
    symbol: str = "AAPL",
    side: str = "buy",
    qty: Decimal = Decimal("100"),
    filled_at: datetime | None = None,
) -> AlpacaOrder:
    """Create a test order."""
    if filled_at is None:
        filled_at = datetime.now() - timedelta(days=30)

    return AlpacaOrder(
        id="test-order-id",
        symbol=symbol,
        side=side,
        qty=qty,
        filled_qty=qty,
        status="filled",
        filled_avg_price=Decimal("150.00"),
        submitted_at=filled_at - timedelta(seconds=10),
        filled_at=filled_at,
    )


class TestHarvestRules:
    """Tests for HarvestRules dataclass."""

    def test_default_values(self) -> None:
        """Test default rule values."""
        rules = HarvestRules()
        assert rules.min_loss_usd == Decimal("100")
        assert rules.min_loss_pct == Decimal("3.0")
        assert rules.min_tax_benefit == Decimal("50")
        assert rules.tax_rate == Decimal("0.35")
        assert rules.min_holding_days == 7
        assert rules.max_harvest_pct == Decimal("10.0")
        assert rules.wash_sale_days == 31

    def test_custom_values(self) -> None:
        """Test custom rule values."""
        rules = HarvestRules(
            min_loss_usd=Decimal("200"),
            min_loss_pct=Decimal("5.0"),
            tax_rate=Decimal("0.40"),
        )
        assert rules.min_loss_usd == Decimal("200")
        assert rules.min_loss_pct == Decimal("5.0")
        assert rules.tax_rate == Decimal("0.40")


class TestHarvestEvaluator:
    """Tests for HarvestEvaluator."""

    def test_calculate_loss_pct(self, evaluator: HarvestEvaluator) -> None:
        """Test loss percentage calculation."""
        # 10% loss: bought at $150, now $135
        position = make_position(
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("135.00"),
        )
        loss_pct = evaluator.calculate_loss_pct(position)
        assert loss_pct == Decimal("10.00")

    def test_calculate_loss_pct_no_loss(self, evaluator: HarvestEvaluator) -> None:
        """Test loss percentage when position has gain."""
        position = make_position(
            avg_entry_price=Decimal("100.00"),
            current_price=Decimal("120.00"),
        )
        loss_pct = evaluator.calculate_loss_pct(position)
        assert loss_pct == Decimal("0")

    def test_calculate_tax_benefit(self, evaluator: HarvestEvaluator) -> None:
        """Test tax benefit calculation."""
        # $1000 loss at 35% tax rate = $350 benefit
        benefit = evaluator.calculate_tax_benefit(Decimal("-1000"))
        assert benefit == Decimal("350.00")

        # Works with positive loss value too
        benefit = evaluator.calculate_tax_benefit(Decimal("1000"))
        assert benefit == Decimal("350.00")

    def test_meets_loss_threshold_passes(self, evaluator: HarvestEvaluator) -> None:
        """Test position that meets loss thresholds."""
        # $1000 loss (6.67%) on $15000 position
        position = make_position(
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("140.00"),
        )
        assert evaluator.meets_loss_threshold(position) is True

    def test_meets_loss_threshold_usd_too_low(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position with loss below USD threshold."""
        # $50 loss on $500 position (10% but only $50)
        position = make_position(
            qty=Decimal("10"),
            avg_entry_price=Decimal("50.00"),
            current_price=Decimal("45.00"),
        )
        assert evaluator.meets_loss_threshold(position) is False

    def test_meets_loss_threshold_pct_too_low(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position with loss below percentage threshold."""
        # $150 loss on $15000 position (only 1%)
        position = make_position(
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("148.50"),
        )
        assert evaluator.meets_loss_threshold(position) is False

    def test_meets_loss_threshold_has_gain(self, evaluator: HarvestEvaluator) -> None:
        """Test position with gain doesn't meet threshold."""
        position = make_position(
            avg_entry_price=Decimal("100.00"),
            current_price=Decimal("110.00"),
        )
        assert evaluator.meets_loss_threshold(position) is False

    def test_meets_tax_benefit_threshold(self, evaluator: HarvestEvaluator) -> None:
        """Test tax benefit threshold check."""
        # $200 loss = $70 benefit (meets $50 threshold)
        position = make_position(
            qty=Decimal("20"),
            avg_entry_price=Decimal("100.00"),
            current_price=Decimal("90.00"),
        )
        assert evaluator.meets_tax_benefit_threshold(position) is True

    def test_meets_tax_benefit_threshold_too_low(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test tax benefit below threshold."""
        # $100 loss = $35 benefit (below $50 threshold)
        position = make_position(
            qty=Decimal("10"),
            avg_entry_price=Decimal("100.00"),
            current_price=Decimal("90.00"),
        )
        assert evaluator.meets_tax_benefit_threshold(position) is False

    def test_get_holding_days(self, evaluator: HarvestEvaluator) -> None:
        """Test holding days calculation."""
        buy_date = datetime.now() - timedelta(days=30)
        orders = [make_order(symbol="AAPL", filled_at=buy_date)]

        days = evaluator.get_holding_days("AAPL", orders)
        assert days == 30

    def test_get_holding_days_no_orders(self, evaluator: HarvestEvaluator) -> None:
        """Test holding days when no orders exist."""
        days = evaluator.get_holding_days("AAPL", [])
        assert days is None

    def test_get_holding_days_different_ticker(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test holding days ignores other tickers."""
        orders = [make_order(symbol="GOOGL")]
        days = evaluator.get_holding_days("AAPL", orders)
        assert days is None

    def test_meets_holding_period(self, evaluator: HarvestEvaluator) -> None:
        """Test holding period check."""
        # Bought 30 days ago (meets 7 day minimum)
        buy_date = datetime.now() - timedelta(days=30)
        orders = [make_order(symbol="AAPL", filled_at=buy_date)]

        assert evaluator.meets_holding_period("AAPL", orders) is True

    def test_meets_holding_period_too_short(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test holding period when too recently bought."""
        # Bought 3 days ago (below 7 day minimum)
        buy_date = datetime.now() - timedelta(days=3)
        orders = [make_order(symbol="AAPL", filled_at=buy_date)]

        assert evaluator.meets_holding_period("AAPL", orders) is False

    def test_meets_holding_period_no_history(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test holding period allowed when no history."""
        assert evaluator.meets_holding_period("AAPL", []) is True

    def test_qualifies_for_harvest_all_criteria(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position that meets all harvest criteria."""
        position = make_position(
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("140.00"),  # $1000 loss, 6.67%
        )
        buy_date = datetime.now() - timedelta(days=30)
        orders = [make_order(symbol="AAPL", filled_at=buy_date)]

        assert evaluator.qualifies_for_harvest(position, orders) is True

    def test_qualifies_for_harvest_wash_restricted(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position under wash sale restriction doesn't qualify."""
        position = make_position(
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("140.00"),
        )
        orders = [make_order(symbol="AAPL")]

        assert (
            evaluator.qualifies_for_harvest(position, orders, is_wash_restricted=True)
            is False
        )

    def test_qualifies_for_harvest_fails_loss(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position that fails loss threshold doesn't qualify."""
        position = make_position(
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("160.00"),  # Gain, not loss
        )
        orders = [make_order(symbol="AAPL")]

        assert evaluator.qualifies_for_harvest(position, orders) is False

    def test_qualifies_for_harvest_fails_holding(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test position bought too recently doesn't qualify."""
        position = make_position(
            qty=Decimal("100"),
            avg_entry_price=Decimal("150.00"),
            current_price=Decimal("140.00"),
        )
        # Bought only 2 days ago
        buy_date = datetime.now() - timedelta(days=2)
        orders = [make_order(symbol="AAPL", filled_at=buy_date)]

        assert evaluator.qualifies_for_harvest(position, orders) is False

    def test_get_clear_date(self, evaluator: HarvestEvaluator) -> None:
        """Test wash sale clear date calculation."""
        sale_date = date(2024, 12, 1)
        clear_date = evaluator.get_clear_date(sale_date)
        assert clear_date == date(2025, 1, 1)

    def test_get_clear_date_default_today(self, evaluator: HarvestEvaluator) -> None:
        """Test clear date defaults to 31 days from today."""
        clear_date = evaluator.get_clear_date()
        expected = date.today() + timedelta(days=31)
        assert clear_date == expected

    def test_apply_portfolio_limit(self, evaluator: HarvestEvaluator) -> None:
        """Test portfolio limit application."""
        # Total portfolio: $100,000
        # Max harvest: 10% = $10,000
        total_value = Decimal("100000")

        pos1 = make_position(
            symbol="AAPL",
            qty=Decimal("50"),
            current_price=Decimal("100"),  # $5000 value
        )
        pos2 = make_position(
            symbol="GOOGL",
            qty=Decimal("30"),
            current_price=Decimal("100"),  # $3000 value
        )
        pos3 = make_position(
            symbol="MSFT",
            qty=Decimal("40"),
            current_price=Decimal("100"),  # $4000 value
        )

        opportunities = [
            (pos1, Decimal("100")),
            (pos2, Decimal("80")),
            (pos3, Decimal("60")),
        ]

        result = evaluator.apply_portfolio_limit(opportunities, total_value)

        # Should include pos1 ($5000) and pos2 ($3000) = $8000
        # pos3 would push to $12000, exceeding limit
        assert len(result) == 2
        assert result[0][0].symbol == "AAPL"
        assert result[1][0].symbol == "GOOGL"

    def test_apply_portfolio_limit_all_fit(self, evaluator: HarvestEvaluator) -> None:
        """Test when all opportunities fit within limit."""
        total_value = Decimal("100000")

        pos1 = make_position(
            symbol="AAPL",
            qty=Decimal("10"),
            current_price=Decimal("100"),  # $1000 value
        )
        pos2 = make_position(
            symbol="GOOGL",
            qty=Decimal("10"),
            current_price=Decimal("100"),  # $1000 value
        )

        opportunities = [
            (pos1, Decimal("100")),
            (pos2, Decimal("80")),
        ]

        result = evaluator.apply_portfolio_limit(opportunities, total_value)
        assert len(result) == 2

    def test_apply_portfolio_limit_empty(self, evaluator: HarvestEvaluator) -> None:
        """Test with no opportunities."""
        result = evaluator.apply_portfolio_limit([], Decimal("100000"))
        assert result == []

    def test_apply_portfolio_limit_zero_value(
        self, evaluator: HarvestEvaluator
    ) -> None:
        """Test with zero portfolio value."""
        pos = make_position()
        result = evaluator.apply_portfolio_limit(
            [(pos, Decimal("100"))], Decimal("0")
        )
        assert result == []
