"""Portfolio scanner for tax-loss harvesting opportunities."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from tlh_agent.data.local_store import HarvestQueueItem, LocalStore
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rules import HarvestEvaluator, HarvestRules
from tlh_agent.services.wash_sale import WashSaleService


@dataclass
class HarvestOpportunity:
    """A potential tax-loss harvesting opportunity.

    Represents a position that qualifies for harvesting based on
    the configured rules. All shares will be sold if executed.
    """

    ticker: str
    shares: Decimal
    current_price: Decimal
    avg_cost: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_loss: Decimal
    loss_pct: Decimal
    estimated_tax_benefit: Decimal
    days_held: int | None
    # Status in the harvest queue
    queue_status: str | None = None  # None if not in queue
    queue_id: str | None = None

    @property
    def can_harvest(self) -> bool:
        """Whether this opportunity can be harvested."""
        return self.queue_status is None or self.queue_status == "pending"


@dataclass
class ScanResult:
    """Result of a portfolio scan."""

    opportunities: list[HarvestOpportunity]
    total_potential_benefit: Decimal
    positions_scanned: int
    positions_with_loss: int
    positions_restricted: int
    scan_time: datetime = field(default_factory=datetime.now)


class PortfolioScanner:
    """Scans portfolio for tax-loss harvesting opportunities.

    Evaluates each position against harvest rules and identifies
    candidates for tax-loss harvesting. Considers wash sale
    restrictions and portfolio limits.
    """

    def __init__(
        self,
        portfolio_service: PortfolioService,
        wash_sale_service: WashSaleService,
        store: LocalStore,
        rules: HarvestRules | None = None,
    ) -> None:
        """Initialize scanner.

        Args:
            portfolio_service: Service for portfolio data.
            wash_sale_service: Service for wash sale tracking.
            store: Local store for persistence.
            rules: Harvest rules (uses defaults if not provided).
        """
        self._portfolio = portfolio_service
        self._wash_sale = wash_sale_service
        self._store = store
        self._rules = rules or HarvestRules()
        self._evaluator = HarvestEvaluator(self._rules)

    @property
    def rules(self) -> HarvestRules:
        """Get current harvest rules."""
        return self._rules

    def update_rules(self, rules: HarvestRules) -> None:
        """Update harvest rules.

        Args:
            rules: New rules to use.
        """
        self._rules = rules
        self._evaluator = HarvestEvaluator(rules)

    def scan(self) -> ScanResult:
        """Scan portfolio for harvest opportunities.

        Evaluates all positions and returns those that qualify
        for tax-loss harvesting.

        Returns:
            ScanResult with opportunities and statistics.
        """
        # Get data from Alpaca
        positions = self._portfolio.get_alpaca_positions()
        order_history = self._portfolio.get_alpaca_orders(days=60)

        # Get active restrictions
        active_restrictions = {r.ticker for r in self._wash_sale.get_active_restrictions()}

        # Get existing queue items
        queue_items = {item.ticker: item for item in self._store.get_harvest_queue()}

        opportunities = []
        positions_with_loss = 0
        positions_restricted = 0

        for position in positions:
            # Skip positions with gains
            if position.unrealized_pl >= 0:
                continue

            positions_with_loss += 1

            # Check wash sale restriction
            is_restricted = position.symbol in active_restrictions
            if is_restricted:
                positions_restricted += 1
                continue

            # Check if qualifies for harvest
            if not self._evaluator.qualifies_for_harvest(
                position, order_history, is_wash_restricted=False
            ):
                continue

            # Calculate metrics
            loss_pct = self._evaluator.calculate_loss_pct(position)
            tax_benefit = self._evaluator.calculate_tax_benefit(position.unrealized_pl)
            days_held = self._evaluator.get_holding_days(position.symbol, order_history)

            # Check if already in queue
            queue_item = queue_items.get(position.symbol)

            opportunity = HarvestOpportunity(
                ticker=position.symbol,
                shares=position.qty,
                current_price=position.current_price,
                avg_cost=position.avg_entry_price,
                market_value=position.market_value,
                cost_basis=position.cost_basis,
                unrealized_loss=position.unrealized_pl,
                loss_pct=loss_pct,
                estimated_tax_benefit=tax_benefit,
                days_held=days_held,
                queue_status=queue_item.status if queue_item else None,
                queue_id=queue_item.id if queue_item else None,
            )
            opportunities.append(opportunity)

        # Sort by tax benefit descending
        opportunities.sort(key=lambda o: o.estimated_tax_benefit, reverse=True)

        # Apply portfolio limit
        total_value = self._portfolio.get_total_value()
        if total_value > 0:
            opportunities = self._apply_portfolio_limit(opportunities, total_value)

        # Calculate totals
        total_benefit = sum((o.estimated_tax_benefit for o in opportunities), Decimal("0"))

        return ScanResult(
            opportunities=opportunities,
            total_potential_benefit=total_benefit,
            positions_scanned=len(positions),
            positions_with_loss=positions_with_loss,
            positions_restricted=positions_restricted,
        )

    def _apply_portfolio_limit(
        self,
        opportunities: list[HarvestOpportunity],
        total_value: Decimal,
    ) -> list[HarvestOpportunity]:
        """Apply portfolio percentage limit.

        Args:
            opportunities: List of opportunities sorted by benefit.
            total_value: Total portfolio value.

        Returns:
            Filtered list respecting max_harvest_pct.
        """
        max_harvest_value = total_value * (self._rules.max_harvest_pct / 100)
        result = []
        cumulative_value = Decimal("0")

        for opp in opportunities:
            if cumulative_value + opp.market_value <= max_harvest_value:
                result.append(opp)
                cumulative_value += opp.market_value
            elif cumulative_value >= max_harvest_value:
                break

        return result

    def add_to_queue(self, opportunity: HarvestOpportunity) -> HarvestQueueItem:
        """Add an opportunity to the harvest queue.

        Args:
            opportunity: The opportunity to queue.

        Returns:
            The created queue item.
        """
        item = HarvestQueueItem(
            id=self._store.new_id(),
            ticker=opportunity.ticker,
            shares=opportunity.shares,
            current_price=opportunity.current_price,
            cost_basis=opportunity.cost_basis,
            unrealized_loss=opportunity.unrealized_loss,
            estimated_tax_benefit=opportunity.estimated_tax_benefit,
            status="pending",
        )
        self._store.add_harvest_item(item)
        return item

    def approve_harvest(self, queue_id: str) -> None:
        """Approve a queued harvest.

        Args:
            queue_id: ID of the queue item to approve.
        """
        for item in self._store.get_harvest_queue():
            if item.id == queue_id:
                item.status = "approved"
                self._store.update_harvest_item(item)
                return
        raise ValueError(f"Queue item not found: {queue_id}")

    def reject_harvest(self, queue_id: str) -> None:
        """Reject a queued harvest.

        Args:
            queue_id: ID of the queue item to reject.
        """
        for item in self._store.get_harvest_queue():
            if item.id == queue_id:
                item.status = "rejected"
                self._store.update_harvest_item(item)
                return
        raise ValueError(f"Queue item not found: {queue_id}")

    def get_pending_harvests(self) -> list[HarvestQueueItem]:
        """Get all pending harvest items.

        Returns:
            List of pending queue items.
        """
        return self._store.get_pending_harvests()

    def get_approved_harvests(self) -> list[HarvestQueueItem]:
        """Get all approved harvest items.

        Returns:
            List of approved queue items ready for execution.
        """
        return self._store.get_approved_harvests()

    def clear_expired_queue_items(self) -> int:
        """Remove expired pending harvests.

        Queue items expire after 1 day to ensure prices are current.

        Returns:
            Number of items removed.
        """
        return self._store.clear_expired_harvests()
