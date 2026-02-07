"""Trade queue tool implementations."""

import logging
from decimal import Decimal

from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.tools.base import ToolResult
from tlh_agent.services.trade_queue import TradeAction, TradeQueueService, TradeType

logger = logging.getLogger(__name__)


def get_trade_queue(
    trade_queue: TradeQueueService,
    symbol: str | None = None,
) -> ToolResult:
    """Get pending trades from the trade queue."""
    try:
        trades = trade_queue.get_pending_trades()

        if symbol:
            symbol_upper = symbol.upper()
            trades = [t for t in trades if t.symbol == symbol_upper]

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


def propose_trades(
    trade_queue: TradeQueueService,
    portfolio_service: PortfolioService | None,
    trades: list[dict],
    trade_type: str,
) -> ToolResult:
    """Propose trades for user approval."""
    try:
        type_map = {
            "harvest": TradeType.HARVEST,
            "index_buy": TradeType.INDEX_BUY,
            "rebalance": TradeType.REBALANCE,
        }
        trade_type_enum = type_map.get(trade_type, TradeType.REBALANCE)

        price_map: dict[str, Decimal] = {}
        if portfolio_service:
            positions = portfolio_service.get_positions()
            price_map = {p.ticker: p.current_price for p in positions}

        added_trades = []
        for trade in trades:
            action = TradeAction.BUY if trade["action"] == "buy" else TradeAction.SELL
            current_price = price_map.get(trade["symbol"], Decimal("100"))

            queued = trade_queue.add_trade(
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


def clear_trade_queue(trade_queue: TradeQueueService) -> ToolResult:
    """Clear all trades from the queue."""
    if not trade_queue:
        return ToolResult(
            success=False, data={}, error="Trade queue service not available",
        )

    try:
        count = len(trade_queue.get_all_trades())
        trade_queue.clear_queue()
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


def remove_trades(
    trade_queue: TradeQueueService,
    symbols: list[str],
) -> ToolResult:
    """Remove trades for one or more symbols from the queue."""
    if not trade_queue:
        return ToolResult(
            success=False, data={}, error="Trade queue service not available",
        )

    if not symbols:
        return ToolResult(
            success=False, data={}, error="At least one symbol is required",
        )

    try:
        symbols_upper = {s.upper() for s in symbols}
        trades = trade_queue.get_all_trades()

        removed_by_symbol: dict[str, int] = {}
        total_removed = 0

        for trade in trades:
            if trade.symbol in symbols_upper:
                trade_queue.remove_trade(trade.id)
                removed_by_symbol[trade.symbol] = removed_by_symbol.get(trade.symbol, 0) + 1
                total_removed += 1

        if total_removed == 0:
            return ToolResult(
                success=True,
                data={
                    "trades_removed": 0,
                    "message": f"No trades found for {', '.join(sorted(symbols_upper))}.",
                },
            )

        return ToolResult(
            success=True,
            data={
                "trades_removed": total_removed,
                "removed_by_symbol": removed_by_symbol,
                "message": f"Removed {total_removed} trade(s) for "
                f"{len(removed_by_symbol)} symbol(s).",
            },
        )
    except Exception as e:
        logger.exception("Error in remove_trades")
        return ToolResult(success=False, data={}, error=str(e))
