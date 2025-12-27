"""Claude tool provider for portfolio operations.

Defines tools that Claude can use to interact with portfolio services:
- get_portfolio_summary: Portfolio value, gains/losses
- get_positions: All current positions
- get_harvest_opportunities: TLH-eligible positions
- get_index_allocation: Current vs S&P 500 target
- get_rebalance_plan: Tax-aware rebalancing recommendations
- propose_trades: Propose trades for user approval
"""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tlh_agent.services.claude import ToolDefinition
from tlh_agent.services.index import IndexService
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rebalance import RebalanceService
from tlh_agent.services.scanner import PortfolioScanner
from tlh_agent.services.trade_queue import TradeAction, TradeQueueService, TradeType

logger = logging.getLogger(__name__)


class ToolName(Enum):
    """Available tool names."""

    GET_PORTFOLIO_SUMMARY = "get_portfolio_summary"
    GET_POSITIONS = "get_positions"
    GET_HARVEST_OPPORTUNITIES = "get_harvest_opportunities"
    GET_INDEX_ALLOCATION = "get_index_allocation"
    GET_REBALANCE_PLAN = "get_rebalance_plan"
    GET_TRADE_QUEUE = "get_trade_queue"
    PROPOSE_TRADES = "propose_trades"
    BUY_INDEX = "buy_index"
    CLEAR_TRADE_QUEUE = "clear_trade_queue"
    REMOVE_TRADE = "remove_trade"


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: dict | list | str
    error: str | None = None

    def to_json(self) -> str:
        """Convert to JSON string for Claude."""
        if self.success:
            return json.dumps(self.data, default=str)
        return json.dumps({"error": self.error})


class ClaudeToolProvider:
    """Provides tools for Claude to interact with portfolio services.

    Tools are executed synchronously and return JSON results.
    """

    def __init__(
        self,
        portfolio_service: PortfolioService | None = None,
        scanner: PortfolioScanner | None = None,
        index_service: IndexService | None = None,
        rebalance_service: RebalanceService | None = None,
        trade_queue: TradeQueueService | None = None,
    ) -> None:
        """Initialize the tool provider.

        Args:
            portfolio_service: Portfolio service for positions.
            scanner: Portfolio scanner for harvest opportunities.
            index_service: Index service for S&P 500 tracking.
            rebalance_service: Rebalance service for tax-aware recommendations.
            trade_queue: Trade queue service for managing pending trades.
        """
        self._portfolio_service = portfolio_service
        self._scanner = scanner
        self._index_service = index_service
        self._rebalance_service = rebalance_service
        self._trade_queue = trade_queue or TradeQueueService()

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get all available tool definitions.

        Returns:
            List of tool definitions for Claude.
        """
        return [
            ToolDefinition(
                name=ToolName.GET_PORTFOLIO_SUMMARY.value,
                description=(
                    "Get a summary of the portfolio including total value, "
                    "unrealized gains/losses, and available cash."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.GET_POSITIONS.value,
                description=(
                    "Get all current positions in the portfolio with market values, "
                    "cost basis, and unrealized gains/losses."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "sort_by": {
                            "type": "string",
                            "enum": ["value", "gain", "loss", "symbol"],
                            "description": "How to sort positions. Defaults to value.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of positions to return.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.GET_HARVEST_OPPORTUNITIES.value,
                description=(
                    "Get tax-loss harvesting opportunities. Shows positions with "
                    "unrealized losses that could be sold to realize tax benefits."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "min_loss": {
                            "type": "number",
                            "description": "Minimum loss amount to include. Defaults to 0.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.GET_INDEX_ALLOCATION.value,
                description=(
                    "Get S&P 500 target allocations for direct indexing. "
                    "Returns all 503 stocks with target weights for buying."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "top_n": {
                            "type": "integer",
                            "description": "Number of stocks to return. Default 503.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.GET_REBALANCE_PLAN.value,
                description=(
                    "Get a tax-aware rebalancing plan. Prioritizes selling losers "
                    "and respects wash sale restrictions."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "threshold_pct": {
                            "type": "number",
                            "description": "Minimum deviation % to trigger rebalance. Default 1.0.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.GET_TRADE_QUEUE.value,
                description=(
                    "Get pending trades in the Trade Queue. "
                    "Shows symbol, shares, notional, and trade type."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Filter by symbol (e.g., 'NVDA'). Optional.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name=ToolName.PROPOSE_TRADES.value,
                description=(
                    "Propose trades for user approval. Trades are added to the queue "
                    "and the user must approve them before execution."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "trades": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "action": {"type": "string", "enum": ["buy", "sell"]},
                                    "shares": {"type": "number"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["symbol", "action", "shares", "reason"],
                            },
                            "description": "List of trades to propose.",
                        },
                        "trade_type": {
                            "type": "string",
                            "enum": ["harvest", "index_buy", "rebalance"],
                            "description": "Type of trades being proposed.",
                        },
                    },
                    "required": ["trades", "trade_type"],
                },
            ),
            ToolDefinition(
                name=ToolName.BUY_INDEX.value,
                description=(
                    "Buy all stocks in a market index with a specified investment amount. "
                    "Automatically calculates shares based on market-cap weights. "
                    "USE THIS instead of propose_trades for index buys."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "investment_amount": {
                            "type": "number",
                            "description": "Total dollar amount to invest across all index stocks.",
                        },
                        "index": {
                            "type": "string",
                            "enum": [
                                "sp500", "nasdaq100", "dowjones",
                                "russell1000", "russell2000", "russell3000",
                            ],
                            "description": "Which index to buy. Defaults to sp500.",
                        },
                    },
                    "required": ["investment_amount"],
                },
            ),
            ToolDefinition(
                name=ToolName.CLEAR_TRADE_QUEUE.value,
                description=(
                    "Clear all pending trades from the trade queue. "
                    "Use this when the user wants to cancel all pending trades or start fresh."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            ToolDefinition(
                name=ToolName.REMOVE_TRADE.value,
                description=(
                    "Remove specific trades from the queue by symbol. "
                    "Use this to cancel trades for a specific stock."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock symbol to remove (e.g., 'AAPL').",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            ToolResult with success status and data.
        """
        try:
            if tool_name == ToolName.GET_PORTFOLIO_SUMMARY.value:
                return self._get_portfolio_summary()
            elif tool_name == ToolName.GET_POSITIONS.value:
                return self._get_positions(
                    sort_by=arguments.get("sort_by", "value"),
                    limit=arguments.get("limit"),
                )
            elif tool_name == ToolName.GET_HARVEST_OPPORTUNITIES.value:
                return self._get_harvest_opportunities(
                    min_loss=Decimal(str(arguments.get("min_loss", 0))),
                )
            elif tool_name == ToolName.GET_INDEX_ALLOCATION.value:
                return self._get_index_allocation(
                    top_n=arguments.get("top_n", 503),
                )
            elif tool_name == ToolName.GET_REBALANCE_PLAN.value:
                return self._get_rebalance_plan(
                    threshold_pct=Decimal(str(arguments.get("threshold_pct", 1.0))),
                )
            elif tool_name == ToolName.GET_TRADE_QUEUE.value:
                return self._get_trade_queue(
                    symbol=arguments.get("symbol"),
                )
            elif tool_name == ToolName.PROPOSE_TRADES.value:
                return self._propose_trades(
                    trades=arguments.get("trades", []),
                    trade_type=arguments.get("trade_type", "rebalance"),
                )
            elif tool_name == ToolName.BUY_INDEX.value:
                return self._buy_index(
                    investment_amount=Decimal(str(arguments.get("investment_amount", 0))),
                    index_name=arguments.get("index", "sp500"),
                )
            elif tool_name == ToolName.CLEAR_TRADE_QUEUE.value:
                return self._clear_trade_queue()
            elif tool_name == ToolName.REMOVE_TRADE.value:
                return self._remove_trade(symbol=arguments.get("symbol", ""))
            else:
                return ToolResult(success=False, data={}, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return ToolResult(success=False, data={}, error=str(e))

    def _get_portfolio_summary(self) -> ToolResult:
        """Get portfolio summary."""
        if not self._portfolio_service:
            return ToolResult(
                success=False,
                data={},
                error="Portfolio service not available",
            )

        try:
            positions = self._portfolio_service.get_positions()

            # Calculate totals
            total_value = sum(p.market_value for p in positions)
            total_gain = sum(
                p.unrealized_gain_loss for p in positions if p.unrealized_gain_loss > 0
            )
            total_loss = sum(
                p.unrealized_gain_loss for p in positions if p.unrealized_gain_loss < 0
            )

            # Get harvest opportunities if scanner available
            harvest_count = 0
            total_harvest_benefit = Decimal("0")
            if self._scanner:
                scan_result = self._scanner.scan()
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

    def _get_positions(
        self,
        sort_by: str = "value",
        limit: int | None = None,
    ) -> ToolResult:
        """Get portfolio positions."""
        if not self._portfolio_service:
            return ToolResult(
                success=False,
                data={},
                error="Portfolio service not available",
            )

        try:
            positions = self._portfolio_service.get_positions()

            # Sort positions
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

            # Apply limit
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

    def _get_harvest_opportunities(self, min_loss: Decimal = Decimal("0")) -> ToolResult:
        """Get tax-loss harvesting opportunities."""
        if not self._scanner:
            return ToolResult(
                success=False,
                data={},
                error="Portfolio scanner not available",
            )

        try:
            scan_result = self._scanner.scan()
            opportunities = [
                o for o in scan_result.opportunities
                if o.unrealized_loss >= min_loss
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

    def _get_index_allocation(self, top_n: int = 503) -> ToolResult:
        """Get index allocation comparison."""
        if not self._index_service or not self._portfolio_service:
            return ToolResult(
                success=False,
                data={},
                error="Index service or portfolio service not available",
            )

        try:
            # Get current positions
            positions = self._portfolio_service.get_positions()
            portfolio_value = sum((p.market_value for p in positions), Decimal(0))

            # Get index constituents
            from tlh_agent.services.index import Position as IndexPosition
            current_positions = [
                IndexPosition(symbol=p.ticker, market_value=p.market_value)
                for p in positions
            ]

            # Calculate allocations
            constituents = self._index_service.get_constituents()
            allocations = self._index_service.calculate_target_allocations(
                portfolio_value=portfolio_value,
                current_positions=current_positions,
                constituents=constituents,
            )

            # Get top deviations
            top_allocations = allocations[:top_n]

            # Return compact format to minimize tokens
            # Format: {symbol: weight} for each stock
            weights = {a.symbol: round(float(a.target_weight), 4) for a in top_allocations}

            return ToolResult(
                success=True,
                data={
                    "portfolio_value": float(portfolio_value),
                    "stock_count": len(constituents),
                    "weights": weights,
                    "note": "Weights are %. Shares = (investment * weight / 100) / price",
                },
            )
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _get_rebalance_plan(self, threshold_pct: Decimal = Decimal("1.0")) -> ToolResult:
        """Get tax-aware rebalance plan."""
        if not self._rebalance_service:
            return ToolResult(
                success=False,
                data={},
                error="Rebalance service not available",
            )

        try:
            plan = self._rebalance_service.generate_rebalance_plan(threshold_pct=threshold_pct)

            return ToolResult(
                success=True,
                data={
                    "total_buys": float(plan.total_buys),
                    "total_sells": float(plan.total_sells),
                    "net_cash_flow": float(plan.net_cash_flow),
                    "estimated_tax_savings": float(plan.estimated_tax_savings),
                    "blocked_trades": plan.blocked_trades,
                    "recommendations": [
                        {
                            "symbol": r.symbol,
                            "name": r.name,
                            "action": r.action.value,
                            "shares": float(r.shares),
                            "notional": float(r.notional),
                            "reason": r.reason,
                            "tax_impact": float(r.tax_impact) if r.tax_impact else None,
                            "wash_sale_blocked": r.wash_sale_blocked,
                            "current_price": float(r.current_price),
                            "priority": r.priority,
                        }
                        for r in plan.recommendations
                    ],
                },
            )
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _get_trade_queue(self, symbol: str | None = None) -> ToolResult:
        """Get pending trades from the trade queue.

        Args:
            symbol: Optional symbol to filter by.

        Returns:
            ToolResult with pending trades.
        """
        try:
            trades = self._trade_queue.get_pending_trades()

            # Filter by symbol if provided
            if symbol:
                symbol_upper = symbol.upper()
                trades = [t for t in trades if t.symbol == symbol_upper]

            # Format for response
            trade_list = [
                {
                    "symbol": t.symbol,
                    "name": t.name,
                    "action": t.action.value,
                    "shares": float(t.shares),
                    "notional": float(t.notional),
                    "trade_type": t.trade_type.value,
                    "reason": t.reason,
                }
                for t in trades
            ]

            return ToolResult(
                success=True,
                data={
                    "pending_count": len(trade_list),
                    "trades": trade_list,
                },
            )
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _propose_trades(
        self,
        trades: list[dict],
        trade_type: str,
    ) -> ToolResult:
        """Propose trades for user approval."""
        try:
            # Map trade type string to enum
            type_map = {
                "harvest": TradeType.HARVEST,
                "index_buy": TradeType.INDEX_BUY,
                "rebalance": TradeType.REBALANCE,
            }
            trade_type_enum = type_map.get(trade_type, TradeType.REBALANCE)

            # Get current prices from portfolio service
            price_map: dict[str, Decimal] = {}
            if self._portfolio_service:
                positions = self._portfolio_service.get_positions()
                price_map = {p.ticker: p.current_price for p in positions}

            added_trades = []
            for trade in trades:
                action = TradeAction.BUY if trade["action"] == "buy" else TradeAction.SELL

                # Get current price (use placeholder if not available)
                current_price = price_map.get(trade["symbol"], Decimal("100"))

                queued = self._trade_queue.add_trade(
                    trade_type=trade_type_enum,
                    action=action,
                    symbol=trade["symbol"],
                    name=trade.get("name", trade["symbol"]),
                    shares=Decimal(str(trade["shares"])),
                    current_price=current_price,
                    reason=trade["reason"],
                )
                added_trades.append({
                    "id": queued.id,
                    "symbol": queued.symbol,
                    "action": queued.action.value,
                    "shares": float(queued.shares),
                    "notional": float(queued.notional),
                })

            return ToolResult(
                success=True,
                data={
                    "trades_added": len(added_trades),
                    "trades": added_trades,
                    "message": f"Added {len(added_trades)} trades to the queue for approval.",
                },
            )
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _buy_index(self, investment_amount: Decimal, index_name: str = "sp500") -> ToolResult:
        """Buy all stocks in an index with market-cap weighted allocation.

        Args:
            investment_amount: Total dollar amount to invest.
            index_name: Which index to buy (sp500, nasdaq100, dowjones, etc.)

        Returns:
            ToolResult with trades added to queue.
        """
        if not self._index_service:
            return ToolResult(
                success=False,
                data={},
                error="Index service not available",
            )

        # Map index names to display names
        index_display_names = {
            "sp500": "S&P 500",
            "nasdaq100": "Nasdaq 100",
            "dowjones": "Dow Jones",
            "russell1000": "Russell 1000",
            "russell2000": "Russell 2000",
            "russell3000": "Russell 3000",
        }
        display_name = index_display_names.get(index_name, index_name.upper())

        # Currently only S&P 500 is fully implemented
        if index_name != "sp500":
            return ToolResult(
                success=False,
                data={},
                error=f"{display_name} not yet implemented. Only S&P 500 available.",
            )

        try:
            # Get all index constituents
            constituents = self._index_service.get_constituents()

            if not constituents:
                return ToolResult(
                    success=False,
                    data={},
                    error="No index constituents available",
                )

            added_trades = []
            total_invested = Decimal("0")

            # Get current prices if portfolio service available
            prices: dict[str, Decimal] = {}
            if self._portfolio_service:
                positions = self._portfolio_service.get_positions()
                for pos in positions:
                    prices[pos.ticker] = pos.current_price

            for constituent in constituents:
                # Calculate dollar amount for this stock
                dollar_amount = investment_amount * constituent.weight / Decimal("100")

                # Get real price from positions, or fetch quote
                current_price = prices.get(constituent.symbol)
                if not current_price and self._portfolio_service:
                    alpaca = getattr(self._portfolio_service, "_alpaca", None)
                    if alpaca:
                        try:
                            quote = alpaca.get_quote(constituent.symbol)
                            current_price = quote if quote else Decimal("100")
                        except Exception:
                            current_price = Decimal("100")  # Fallback
                if not current_price:
                    current_price = Decimal("100")  # Final fallback

                # Calculate shares (allow fractional)
                shares = dollar_amount / current_price

                if shares > Decimal("0.0001"):  # Skip tiny positions
                    queued = self._trade_queue.add_trade(
                        trade_type=TradeType.INDEX_BUY,
                        action=TradeAction.BUY,
                        symbol=constituent.symbol,
                        name=constituent.name,
                        shares=shares.quantize(Decimal("0.0001")),
                        current_price=current_price,
                        reason=f"S&P 500 index buy ({float(constituent.weight):.2f}% weight)",
                    )
                    added_trades.append({
                        "symbol": queued.symbol,
                        "shares": float(queued.shares),
                        "notional": float(queued.notional),
                    })
                    total_invested += queued.notional

            return ToolResult(
                success=True,
                data={
                    "trades_added": len(added_trades),
                    "total_invested": float(total_invested),
                    "message": f"Added {len(added_trades)} trades to queue.",
                },
            )
        except Exception as e:
            logger.exception("Error in buy_index")
            return ToolResult(success=False, data={}, error=str(e))

    def _clear_trade_queue(self) -> ToolResult:
        """Clear all trades from the queue.

        Returns:
            ToolResult with count of cleared trades.
        """
        if not self._trade_queue:
            return ToolResult(
                success=False,
                data={},
                error="Trade queue service not available",
            )

        try:
            count = len(self._trade_queue.get_all_trades())
            self._trade_queue.clear_queue()
            return ToolResult(
                success=True,
                data={
                    "trades_cleared": count,
                    "message": f"Cleared {count} trades from queue.",
                },
            )
        except Exception as e:
            logger.exception("Error in clear_trade_queue")
            return ToolResult(success=False, data={}, error=str(e))

    def _remove_trade(self, symbol: str) -> ToolResult:
        """Remove trades for a specific symbol from the queue.

        Args:
            symbol: Stock symbol to remove.

        Returns:
            ToolResult with count of removed trades.
        """
        if not self._trade_queue:
            return ToolResult(
                success=False,
                data={},
                error="Trade queue service not available",
            )

        if not symbol:
            return ToolResult(
                success=False,
                data={},
                error="Symbol is required",
            )

        try:
            symbol_upper = symbol.upper()
            trades = self._trade_queue.get_all_trades()
            removed = 0

            for trade in trades:
                if trade.symbol == symbol_upper:
                    self._trade_queue.remove_trade(trade.id)
                    removed += 1

            if removed == 0:
                return ToolResult(
                    success=True,
                    data={
                        "trades_removed": 0,
                        "message": f"No trades found for {symbol_upper}.",
                    },
                )

            return ToolResult(
                success=True,
                data={
                    "trades_removed": removed,
                    "message": f"Removed {removed} trade(s) for {symbol_upper}.",
                },
            )
        except Exception as e:
            logger.exception("Error in remove_trade")
            return ToolResult(success=False, data={}, error=str(e))
