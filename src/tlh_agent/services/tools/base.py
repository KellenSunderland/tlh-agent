"""Shared types for Claude tools."""

import json
from dataclasses import dataclass
from enum import Enum


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
    REBALANCE_TO_TARGET = "rebalance_to_target"


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
