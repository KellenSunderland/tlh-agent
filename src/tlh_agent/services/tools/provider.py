"""Claude tool provider — thin dispatcher over domain tool modules."""

import logging
from decimal import Decimal

from tlh_agent.services.claude import ToolDefinition
from tlh_agent.services.index import IndexService
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rebalance import RebalanceService
from tlh_agent.services.scanner import PortfolioScanner
from tlh_agent.services.tools import index as index_tools
from tlh_agent.services.tools import portfolio as portfolio_tools
from tlh_agent.services.tools import queue as queue_tools
from tlh_agent.services.tools.base import ToolName, ToolResult
from tlh_agent.services.trade_queue import TradeQueueService

logger = logging.getLogger(__name__)


class ClaudeToolProvider:
    """Provides tools for Claude to interact with portfolio services."""

    def __init__(
        self,
        portfolio_service: PortfolioService | None = None,
        scanner: PortfolioScanner | None = None,
        index_service: IndexService | None = None,
        rebalance_service: RebalanceService | None = None,
        trade_queue: TradeQueueService | None = None,
    ) -> None:
        self._portfolio_service = portfolio_service
        self._scanner = scanner
        self._index_service = index_service
        self._rebalance_service = rebalance_service
        self._trade_queue = trade_queue or TradeQueueService()

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get all available tool definitions for Claude."""
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
                    "Remove trades from the queue by symbol(s). "
                    "Can remove a single stock or multiple stocks at once."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "List of stock symbols to remove "
                                "(e.g., ['AAPL', 'MSFT', 'GOOGL'])."
                            ),
                        },
                    },
                    "required": ["symbols"],
                },
            ),
            ToolDefinition(
                name=ToolName.REBALANCE_TO_TARGET.value,
                description=(
                    "Calculate trades needed to rebalance portfolio to a target value "
                    "with holdings matching an index (default S&P 500). "
                    "This will propose SELL orders for overweight/unwanted positions "
                    "and BUY orders for underweight positions. Use this when the user "
                    "wants to rebalance to a specific portfolio value."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_value": {
                            "type": "number",
                            "description": (
                                "Target total portfolio value in dollars "
                                "(e.g., 100000 for $100k)."
                            ),
                        },
                        "index": {
                            "type": "string",
                            "description": "Index to match (default 'sp500').",
                            "default": "sp500",
                        },
                    },
                    "required": ["target_value"],
                },
            ),
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute a tool and return the result."""
        try:
            if tool_name == ToolName.GET_PORTFOLIO_SUMMARY.value:
                return portfolio_tools.get_portfolio_summary(
                    self._portfolio_service, self._scanner,
                )
            elif tool_name == ToolName.GET_POSITIONS.value:
                return portfolio_tools.get_positions(
                    self._portfolio_service,
                    sort_by=arguments.get("sort_by", "value"),
                    limit=arguments.get("limit"),
                )
            elif tool_name == ToolName.GET_HARVEST_OPPORTUNITIES.value:
                return portfolio_tools.get_harvest_opportunities(
                    self._scanner,
                    min_loss=Decimal(str(arguments.get("min_loss", 0))),
                )
            elif tool_name == ToolName.GET_INDEX_ALLOCATION.value:
                return index_tools.get_index_allocation(
                    self._index_service,
                    self._portfolio_service,
                    top_n=arguments.get("top_n", 503),
                )
            elif tool_name == ToolName.GET_REBALANCE_PLAN.value:
                return index_tools.get_rebalance_plan(
                    self._rebalance_service,
                    threshold_pct=Decimal(str(arguments.get("threshold_pct", 1.0))),
                )
            elif tool_name == ToolName.GET_TRADE_QUEUE.value:
                return queue_tools.get_trade_queue(
                    self._trade_queue,
                    symbol=arguments.get("symbol"),
                )
            elif tool_name == ToolName.PROPOSE_TRADES.value:
                return queue_tools.propose_trades(
                    self._trade_queue,
                    self._portfolio_service,
                    trades=arguments.get("trades", []),
                    trade_type=arguments.get("trade_type", "rebalance"),
                )
            elif tool_name == ToolName.BUY_INDEX.value:
                return index_tools.buy_index(
                    self._index_service,
                    self._portfolio_service,
                    self._trade_queue,
                    investment_amount=Decimal(str(arguments.get("investment_amount", 0))),
                    index_name=arguments.get("index", "sp500"),
                )
            elif tool_name == ToolName.CLEAR_TRADE_QUEUE.value:
                return queue_tools.clear_trade_queue(self._trade_queue)
            elif tool_name == ToolName.REMOVE_TRADE.value:
                return queue_tools.remove_trades(
                    self._trade_queue,
                    symbols=arguments.get("symbols", []),
                )
            elif tool_name == ToolName.REBALANCE_TO_TARGET.value:
                return index_tools.rebalance_to_target(
                    self._portfolio_service,
                    self._index_service,
                    self._trade_queue,
                    target_value=Decimal(str(arguments.get("target_value", 0))),
                    index_name=arguments.get("index", "sp500"),
                )
            else:
                return ToolResult(success=False, data={}, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return ToolResult(success=False, data={}, error=str(e))
