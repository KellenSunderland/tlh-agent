"""Portfolio-related tool implementations."""

import logging
from decimal import Decimal

from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.scanner import PortfolioScanner
from tlh_agent.services.tools.base import ToolResult

logger = logging.getLogger(__name__)


def get_portfolio_summary(
    portfolio_service: PortfolioService | None,
    scanner: PortfolioScanner | None,
) -> ToolResult:
    """Get portfolio summary including value, gains/losses, and harvest opportunities."""
    if not portfolio_service:
        return ToolResult(success=False, data={}, error="Portfolio service not available")

    try:
        positions = portfolio_service.get_positions()

        total_value = sum(p.market_value for p in positions)
        total_gain = sum(
            p.unrealized_gain_loss for p in positions if p.unrealized_gain_loss > 0
        )
        total_loss = sum(
            p.unrealized_gain_loss for p in positions if p.unrealized_gain_loss < 0
        )

        harvest_count = 0
        total_harvest_benefit = Decimal("0")
        if scanner:
            scan_result = scanner.scan()
            harvest_count = len(scan_result.opportunities)
            total_harvest_benefit = sum(
                o.estimated_tax_benefit for o in scan_result.opportunities
            )

        return ToolResult(
            success=True,
            data={
                "total_value": float(total_value),
                "total_unrealized_gain": float(total_gain),
                "total_unrealized_loss": float(total_loss),
                "net_unrealized": float(total_gain + total_loss),
                "position_count": len(positions),
                "harvest_opportunities": harvest_count,
                "potential_tax_savings": float(total_harvest_benefit),
            },
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


def get_positions(
    portfolio_service: PortfolioService | None,
    sort_by: str = "value",
    limit: int | None = None,
) -> ToolResult:
    """Get portfolio positions with optional sorting and limit."""
    if not portfolio_service:
        return ToolResult(success=False, data={}, error="Portfolio service not available")

    try:
        positions = portfolio_service.get_positions()

        if sort_by == "gain":
            positions = sorted(
                positions, key=lambda p: p.unrealized_gain_loss, reverse=True
            )
        elif sort_by == "loss":
            positions = sorted(positions, key=lambda p: p.unrealized_gain_loss)
        elif sort_by == "symbol":
            positions = sorted(positions, key=lambda p: p.ticker)
        else:  # value
            positions = sorted(positions, key=lambda p: p.market_value, reverse=True)

        if limit:
            positions = positions[:limit]

        return ToolResult(
            success=True,
            data=[
                {
                    "symbol": p.ticker,
                    "name": p.name,
                    "shares": float(p.shares),
                    "market_value": float(p.market_value),
                    "cost_basis": float(p.cost_basis),
                    "unrealized_gain": float(p.unrealized_gain_loss),
                    "unrealized_gain_pct": float(p.unrealized_gain_loss_pct),
                }
                for p in positions
            ],
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


def get_harvest_opportunities(
    scanner: PortfolioScanner | None,
    min_loss: Decimal = Decimal("0"),
) -> ToolResult:
    """Get tax-loss harvesting opportunities."""
    if not scanner:
        return ToolResult(success=False, data={}, error="Portfolio scanner not available")

    try:
        scan_result = scanner.scan()
        opportunities = [
            o for o in scan_result.opportunities
            if o.unrealized_loss <= -min_loss
        ]

        return ToolResult(
            success=True,
            data=[
                {
                    "symbol": o.ticker,
                    "shares": float(o.shares),
                    "current_price": float(o.current_price),
                    "avg_cost": float(o.avg_cost),
                    "market_value": float(o.market_value),
                    "cost_basis": float(o.cost_basis),
                    "unrealized_loss": float(o.unrealized_loss),
                    "loss_pct": float(o.loss_pct),
                    "estimated_tax_benefit": float(o.estimated_tax_benefit),
                    "days_held": o.days_held,
                    "queue_status": o.queue_status,
                }
                for o in opportunities
            ],
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))
