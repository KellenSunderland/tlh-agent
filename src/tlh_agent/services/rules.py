"""Harvest rules configuration and evaluation for TLH Agent."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from tlh_agent.brokers.alpaca import AlpacaOrder, AlpacaPosition


@dataclass
class HarvestRules:
    """Configuration for tax-loss harvesting rules.

    These rules determine which positions qualify for harvesting.
    """

    # Minimum unrealized loss in USD to consider harvesting
    min_loss_usd: Decimal = field(default_factory=lambda: Decimal("100"))

    # Minimum loss as percentage of position value
    min_loss_pct: Decimal = field(default_factory=lambda: Decimal("3.0"))

    # Minimum estimated tax benefit to harvest
    min_tax_benefit: Decimal = field(default_factory=lambda: Decimal("50"))

    # Tax rate for benefit calculation (default 35%)
    tax_rate: Decimal = field(default_factory=lambda: Decimal("0.35"))

    # Minimum days held before harvesting (avoid very recent buys)
    min_holding_days: int = 7

    # Maximum portfolio percentage to harvest in one scan
    max_harvest_pct: Decimal = field(default_factory=lambda: Decimal("10.0"))

    # Days to wait before rebuy (wash sale period)
    wash_sale_days: int = 31


class HarvestEvaluator:
    """Evaluates positions against harvest rules."""

    def __init__(self, rules: HarvestRules) -> None:
        """Initialize evaluator with rules.

        Args:
            rules: Harvest rules configuration.
        """
        self._rules = rules

    @property
    def rules(self) -> HarvestRules:
        """Get the current rules."""
        return self._rules

    def calculate_loss_pct(self, position: AlpacaPosition) -> Decimal:
        """Calculate the loss percentage for a position.

        Args:
            position: The position to evaluate.

        Returns:
            Loss as a positive percentage (e.g., 5.0 for 5% loss).
            Returns 0 if position has a gain.
        """
        if position.unrealized_pl >= 0:
            return Decimal("0")

        # Loss percentage = abs(loss) / cost_basis * 100
        if position.cost_basis == 0:
            return Decimal("0")

        loss_pct = (abs(position.unrealized_pl) / position.cost_basis) * 100
        return loss_pct.quantize(Decimal("0.01"))

    def calculate_tax_benefit(self, loss: Decimal) -> Decimal:
        """Calculate estimated tax benefit from a loss.

        Args:
            loss: The unrealized loss (negative or positive magnitude).

        Returns:
            Estimated tax benefit in USD.
        """
        # Ensure we're working with positive loss value
        loss_amount = abs(loss)
        benefit = loss_amount * self._rules.tax_rate
        return benefit.quantize(Decimal("0.01"))

    def meets_loss_threshold(self, position: AlpacaPosition) -> bool:
        """Check if position meets minimum loss thresholds.

        Both USD and percentage thresholds must be met.

        Args:
            position: The position to evaluate.

        Returns:
            True if position meets loss thresholds.
        """
        # Must have an unrealized loss
        if position.unrealized_pl >= 0:
            return False

        # Check USD threshold
        loss_usd = abs(position.unrealized_pl)
        if loss_usd < self._rules.min_loss_usd:
            return False

        # Check percentage threshold
        loss_pct = self.calculate_loss_pct(position)
        return loss_pct >= self._rules.min_loss_pct

    def meets_tax_benefit_threshold(self, position: AlpacaPosition) -> bool:
        """Check if position meets minimum tax benefit threshold.

        Args:
            position: The position to evaluate.

        Returns:
            True if tax benefit meets minimum.
        """
        if position.unrealized_pl >= 0:
            return False

        benefit = self.calculate_tax_benefit(position.unrealized_pl)
        return benefit >= self._rules.min_tax_benefit

    def get_holding_days(
        self, ticker: str, order_history: list[AlpacaOrder]
    ) -> int | None:
        """Get the number of days the position has been held.

        Uses the most recent buy order to determine holding period.

        Args:
            ticker: The stock symbol.
            order_history: List of historical orders.

        Returns:
            Days since last buy, or None if no buy found.
        """
        # Find most recent buy order for this ticker
        buy_orders = [
            o
            for o in order_history
            if o.symbol == ticker and o.side == "buy" and o.filled_at is not None
        ]

        if not buy_orders:
            return None

        # Sort by filled date descending and get most recent
        buy_orders.sort(key=lambda o: o.filled_at, reverse=True)  # type: ignore[arg-type, return-value]
        most_recent_buy = buy_orders[0]

        if most_recent_buy.filled_at is None:
            return None

        # Calculate days held
        today = date.today()
        buy_date = most_recent_buy.filled_at.date()
        return (today - buy_date).days

    def meets_holding_period(
        self, ticker: str, order_history: list[AlpacaOrder]
    ) -> bool:
        """Check if position meets minimum holding period.

        Args:
            ticker: The stock symbol.
            order_history: List of historical orders.

        Returns:
            True if position has been held long enough.
        """
        days_held = self.get_holding_days(ticker, order_history)

        # If we can't determine holding period, allow harvest
        # (position may predate order history)
        if days_held is None:
            return True

        return days_held >= self._rules.min_holding_days

    def qualifies_for_harvest(
        self,
        position: AlpacaPosition,
        order_history: list[AlpacaOrder],
        is_wash_restricted: bool = False,
    ) -> bool:
        """Check if a position qualifies for tax-loss harvesting.

        A position qualifies if it:
        - Has an unrealized loss meeting thresholds
        - Meets minimum tax benefit
        - Has been held long enough
        - Is not under wash sale restriction

        Args:
            position: The position to evaluate.
            order_history: Historical orders for holding period check.
            is_wash_restricted: Whether ticker is under wash sale restriction.

        Returns:
            True if position qualifies for harvesting.
        """
        # Cannot harvest if under wash sale restriction
        if is_wash_restricted:
            return False

        # Must meet loss thresholds
        if not self.meets_loss_threshold(position):
            return False

        # Must meet tax benefit threshold
        if not self.meets_tax_benefit_threshold(position):
            return False

        # Must meet holding period
        return self.meets_holding_period(position.symbol, order_history)

    def get_clear_date(self, sale_date: date | None = None) -> date:
        """Get the date when a sold security can be repurchased.

        Args:
            sale_date: Date of sale (defaults to today).

        Returns:
            Date when wash sale period ends.
        """
        if sale_date is None:
            sale_date = date.today()
        return sale_date + timedelta(days=self._rules.wash_sale_days)

    def apply_portfolio_limit(
        self, opportunities: list[tuple[AlpacaPosition, Decimal]], total_value: Decimal
    ) -> list[tuple[AlpacaPosition, Decimal]]:
        """Apply portfolio percentage limit to harvest opportunities.

        Takes a list of (position, tax_benefit) tuples sorted by priority
        and returns the subset that fits within the portfolio limit.

        Args:
            opportunities: List of (position, tax_benefit) tuples.
            total_value: Total portfolio value.

        Returns:
            Filtered list respecting max_harvest_pct limit.
        """
        if total_value <= 0:
            return []

        max_harvest_value = total_value * (self._rules.max_harvest_pct / 100)
        result = []
        cumulative_value = Decimal("0")

        for position, benefit in opportunities:
            position_value = position.market_value
            if cumulative_value + position_value <= max_harvest_value:
                result.append((position, benefit))
                cumulative_value += position_value
            # Stop if we can't fit any more
            elif cumulative_value >= max_harvest_value:
                break

        return result
