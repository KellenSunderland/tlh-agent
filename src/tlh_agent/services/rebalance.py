"""Tax-aware rebalancing service.

Provides rebalancing recommendations that prioritize tax-loss harvesting
and respect wash sale restrictions.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from tlh_agent.services.index import IndexService, TargetAllocation
from tlh_agent.services.portfolio import PortfolioService, Position
from tlh_agent.services.wash_sale import WashSaleService


class TradeAction(Enum):
    """Type of trade action."""

    BUY = "buy"
    SELL = "sell"


@dataclass
class RebalanceRecommendation:
    """A single trade recommendation for rebalancing."""

    symbol: str
    name: str
    action: TradeAction
    shares: Decimal
    notional: Decimal  # Dollar value
    reason: str
    tax_impact: Decimal | None  # Estimated tax impact (positive = tax owed, negative = tax savings)
    wash_sale_blocked: bool  # True if this trade would trigger wash sale
    current_price: Decimal
    priority: int  # Lower = higher priority


@dataclass
class RebalancePlan:
    """A complete rebalancing plan."""

    recommendations: list[RebalanceRecommendation]
    total_buys: Decimal
    total_sells: Decimal
    net_cash_flow: Decimal  # Positive = cash out, negative = cash needed
    estimated_tax_savings: Decimal
    blocked_trades: int  # Number of trades blocked by wash sale


class RebalanceService:
    """Service for generating tax-aware rebalancing recommendations.

    Prioritizes:
    1. Selling positions with unrealized losses (tax-loss harvesting)
    2. Avoiding wash sale violations
    3. Short-term losses over long-term losses (higher tax benefit)
    4. Rebalancing toward target allocations
    """

    def __init__(
        self,
        portfolio_service: PortfolioService,
        index_service: IndexService,
        wash_sale_service: WashSaleService,
        tax_rate: Decimal = Decimal("0.35"),
    ) -> None:
        """Initialize the rebalance service.

        Args:
            portfolio_service: Portfolio data service.
            index_service: Index tracking service.
            wash_sale_service: Wash sale tracking service.
            tax_rate: Assumed marginal tax rate for tax impact calculations.
        """
        self._portfolio = portfolio_service
        self._index = index_service
        self._wash_sale = wash_sale_service
        self._tax_rate = tax_rate

    def generate_rebalance_plan(
        self,
        target_allocations: list[TargetAllocation] | None = None,
        threshold_pct: Decimal = Decimal("1.0"),
        max_trades: int | None = None,
    ) -> RebalancePlan:
        """Generate a tax-aware rebalancing plan.

        Args:
            target_allocations: Target allocations to rebalance toward.
                If None, uses current index service allocations.
            threshold_pct: Minimum drift percentage to trigger rebalance.
            max_trades: Maximum number of trades to include.

        Returns:
            Complete rebalancing plan with recommendations.
        """
        # Get current positions
        positions = self._portfolio.get_positions()
        positions_by_symbol = {p.ticker: p for p in positions}

        # Get target allocations
        if target_allocations is None:
            portfolio_value = self._portfolio.get_total_value()
            position_list = [
                type("Position", (), {"symbol": p.ticker, "market_value": p.market_value})()
                for p in positions
            ]
            target_allocations = self._index.calculate_target_allocations(
                portfolio_value=portfolio_value,
                current_positions=position_list,
            )

        recommendations: list[RebalanceRecommendation] = []

        for allocation in target_allocations:
            # Skip if within threshold
            if abs(allocation.difference_pct) < threshold_pct:
                continue

            position = positions_by_symbol.get(allocation.symbol)

            if allocation.difference > 0:
                # Need to buy more
                rec = self._create_buy_recommendation(allocation, position)
            else:
                # Need to sell some
                rec = self._create_sell_recommendation(allocation, position)

            if rec:
                recommendations.append(rec)

        # Sort by priority (sells with losses first, then buys)
        recommendations.sort(key=lambda r: r.priority)

        # Apply max trades limit if specified
        if max_trades and len(recommendations) > max_trades:
            recommendations = recommendations[:max_trades]

        # Calculate totals
        total_buys = sum(r.notional for r in recommendations if r.action == TradeAction.BUY)
        total_sells = sum(r.notional for r in recommendations if r.action == TradeAction.SELL)
        net_cash_flow = total_sells - total_buys
        tax_savings = sum(
            r.tax_impact for r in recommendations if r.tax_impact and r.tax_impact < 0
        )
        blocked_trades = sum(1 for r in recommendations if r.wash_sale_blocked)

        return RebalancePlan(
            recommendations=recommendations,
            total_buys=total_buys,
            total_sells=total_sells,
            net_cash_flow=net_cash_flow,
            estimated_tax_savings=abs(tax_savings),
            blocked_trades=blocked_trades,
        )

    def _create_buy_recommendation(
        self,
        allocation: TargetAllocation,
        position: Position | None,
    ) -> RebalanceRecommendation:
        """Create a buy recommendation.

        Args:
            allocation: Target allocation.
            position: Current position if any.

        Returns:
            Buy recommendation.
        """
        current_price = position.current_price if position else Decimal("100")  # Default price
        shares = (allocation.difference / current_price).quantize(Decimal("0.001"))

        # Check if buying would trigger wash sale (if we recently sold)
        is_blocked = self._wash_sale.get_clear_date(allocation.symbol) is not None

        return RebalanceRecommendation(
            symbol=allocation.symbol,
            name=allocation.name,
            action=TradeAction.BUY,
            shares=shares,
            notional=allocation.difference,
            reason=f"Underweight by {allocation.difference_pct:.1f}%",
            tax_impact=None,  # No tax impact on buys
            wash_sale_blocked=is_blocked,
            current_price=current_price,
            priority=100,  # Buys are lower priority than harvesting sells
        )

    def _create_sell_recommendation(
        self,
        allocation: TargetAllocation,
        position: Position | None,
    ) -> RebalanceRecommendation | None:
        """Create a sell recommendation with tax-aware prioritization.

        Args:
            allocation: Target allocation.
            position: Current position.

        Returns:
            Sell recommendation, or None if no position to sell.
        """
        if position is None:
            return None

        sell_amount = abs(allocation.difference)
        shares = (sell_amount / position.current_price).quantize(Decimal("0.001"))

        # Don't sell more shares than we have
        if shares > position.shares:
            shares = position.shares
            sell_amount = shares * position.current_price

        # Calculate unrealized gain/loss for this sale
        cost_basis_per_share = position.cost_basis / position.shares
        unrealized_pl = (position.current_price - cost_basis_per_share) * shares

        # Calculate tax impact
        tax_impact = unrealized_pl * self._tax_rate

        # Determine priority based on tax benefit
        if unrealized_pl < 0:
            # This is a loss - great for tax harvesting
            # More negative = higher priority (lower number)
            priority = int(unrealized_pl)  # Will be negative
            pct = abs(allocation.difference_pct)
            loss = abs(unrealized_pl)
            reason = f"Overweight by {pct:.1f}% - harvest loss ${loss:.2f}"
        else:
            # This is a gain - still do it for rebalancing, but lower priority
            priority = 50 + int(unrealized_pl / 100)  # Positive priority
            reason = f"Overweight by {abs(allocation.difference_pct):.1f}%"

        # Check if this position is under wash sale restriction
        is_blocked = (
            position.wash_sale_until is not None and position.wash_sale_until > date.today()
        )

        return RebalanceRecommendation(
            symbol=allocation.symbol,
            name=allocation.name,
            action=TradeAction.SELL,
            shares=shares,
            notional=sell_amount,
            reason=reason,
            tax_impact=tax_impact,
            wash_sale_blocked=is_blocked,
            current_price=position.current_price,
            priority=priority,
        )

    def get_harvest_opportunities(
        self,
        min_loss: Decimal = Decimal("100"),
    ) -> list[RebalanceRecommendation]:
        """Get positions that can be sold for tax-loss harvesting.

        Args:
            min_loss: Minimum unrealized loss to consider.

        Returns:
            List of sell recommendations for positions with losses.
        """
        positions = self._portfolio.get_positions()
        opportunities = []

        for position in positions:
            # Skip positions with gains
            if position.unrealized_gain_loss >= 0:
                continue

            # Skip if loss is too small
            loss = abs(position.unrealized_gain_loss)
            if loss < min_loss:
                continue

            # Check wash sale restriction
            is_blocked = (
                position.wash_sale_until is not None and position.wash_sale_until > date.today()
            )

            tax_impact = position.unrealized_gain_loss * self._tax_rate

            opportunities.append(
                RebalanceRecommendation(
                    symbol=position.ticker,
                    name=position.name,
                    action=TradeAction.SELL,
                    shares=position.shares,
                    notional=position.market_value,
                    reason=f"Tax-loss harvest - save ${abs(tax_impact):.2f}",
                    tax_impact=tax_impact,
                    wash_sale_blocked=is_blocked,
                    current_price=position.current_price,
                    priority=int(position.unrealized_gain_loss),  # More negative = higher priority
                )
            )

        # Sort by priority (largest losses first)
        opportunities.sort(key=lambda r: r.priority)

        return opportunities

    def estimate_annual_tax_savings(self) -> Decimal:
        """Estimate potential annual tax savings from harvesting.

        Returns:
            Estimated tax savings in dollars.
        """
        opportunities = self.get_harvest_opportunities(min_loss=Decimal("0"))

        total_losses = sum(
            abs(o.tax_impact) for o in opportunities if o.tax_impact and not o.wash_sale_blocked
        )

        return total_losses
