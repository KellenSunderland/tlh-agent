"""Index and rebalance tool implementations."""

import logging
from decimal import Decimal

from tlh_agent.services.index import IndexService
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rebalance import RebalanceService
from tlh_agent.services.tools.base import ToolResult
from tlh_agent.services.trade_queue import TradeAction, TradeQueueService, TradeType

logger = logging.getLogger(__name__)

INDEX_DISPLAY_NAMES = {
    "sp500": "S&P 500",
    "nasdaq100": "Nasdaq 100",
    "dowjones": "Dow Jones",
    "russell1000": "Russell 1000",
    "russell2000": "Russell 2000",
    "russell3000": "Russell 3000",
}


def get_index_allocation(
    index_service: IndexService | None,
    portfolio_service: PortfolioService | None,
    top_n: int = 503,
) -> ToolResult:
    """Get index allocation comparison."""
    if not index_service or not portfolio_service:
        return ToolResult(
            success=False, data={},
            error="Index service or portfolio service not available",
        )

    try:
        positions = portfolio_service.get_positions()
        portfolio_value = sum((p.market_value for p in positions), Decimal(0))

        from tlh_agent.services.index import Position as IndexPosition
        current_positions = [
            IndexPosition(symbol=p.ticker, market_value=p.market_value)
            for p in positions
        ]

        constituents = index_service.get_constituents()
        allocations = index_service.calculate_target_allocations(
            portfolio_value=portfolio_value,
            current_positions=current_positions,
            constituents=constituents,
        )

        top_allocations = allocations[:top_n]
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


def get_rebalance_plan(
    rebalance_service: RebalanceService | None,
    threshold_pct: Decimal = Decimal("1.0"),
) -> ToolResult:
    """Get tax-aware rebalance plan."""
    if not rebalance_service:
        return ToolResult(success=False, data={}, error="Rebalance service not available")

    try:
        plan = rebalance_service.generate_rebalance_plan(threshold_pct=threshold_pct)

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


def buy_index(
    index_service: IndexService | None,
    portfolio_service: PortfolioService | None,
    trade_queue: TradeQueueService,
    investment_amount: Decimal,
    index_name: str = "sp500",
) -> ToolResult:
    """Buy all stocks in an index with market-cap weighted allocation."""
    if not index_service:
        return ToolResult(success=False, data={}, error="Index service not available")

    display_name = INDEX_DISPLAY_NAMES.get(index_name, index_name.upper())

    if index_name != "sp500":
        return ToolResult(
            success=False, data={},
            error=f"{display_name} not yet implemented. Only S&P 500 available.",
        )

    try:
        constituents = index_service.get_constituents()

        if not constituents:
            return ToolResult(success=False, data={}, error="No index constituents available")

        added_trades = []
        total_invested = Decimal("0")

        prices: dict[str, Decimal] = {}
        if portfolio_service:
            positions = portfolio_service.get_positions()
            for pos in positions:
                prices[pos.ticker] = pos.current_price

        for constituent in constituents:
            dollar_amount = investment_amount * constituent.weight / Decimal("100")

            current_price = prices.get(constituent.symbol)
            if not current_price and portfolio_service:
                alpaca = getattr(portfolio_service, "_alpaca", None)
                if alpaca:
                    try:
                        quote = alpaca.get_quote(constituent.symbol)
                        current_price = quote if quote else Decimal("100")
                    except Exception:
                        current_price = Decimal("100")
            if not current_price:
                current_price = Decimal("100")

            shares = dollar_amount / current_price

            if shares > Decimal("0.0001"):
                queued = trade_queue.add_trade(
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


def rebalance_to_target(
    portfolio_service: PortfolioService | None,
    index_service: IndexService | None,
    trade_queue: TradeQueueService,
    target_value: Decimal,
    index_name: str = "sp500",
) -> ToolResult:
    """Rebalance portfolio to a target value matching index weights."""
    if not portfolio_service or not index_service:
        return ToolResult(
            success=False, data={},
            error="Portfolio service or index service not available",
        )

    if index_name != "sp500":
        return ToolResult(
            success=False, data={},
            error=f"{index_name} not yet implemented. Only sp500 available.",
        )

    if target_value <= 0:
        return ToolResult(success=False, data={}, error="Target value must be positive")

    try:
        positions = portfolio_service.get_positions()
        current_holdings: dict[str, dict] = {}
        for pos in positions:
            current_holdings[pos.ticker] = {
                "shares": pos.shares,
                "price": pos.current_price,
                "value": pos.market_value,
                "name": pos.name,
            }

        constituents = index_service.get_constituents()
        index_symbols = {c.symbol for c in constituents}
        weight_by_symbol = {c.symbol: c.weight for c in constituents}
        name_by_symbol = {c.symbol: c.name for c in constituents}

        sells = []
        buys = []
        total_sell_value = Decimal("0")
        total_buy_value = Decimal("0")

        alpaca = getattr(portfolio_service, "_alpaca", None)

        # Step 1: Calculate sells - positions not in index or overweight
        for symbol, holding in current_holdings.items():
            target_weight = weight_by_symbol.get(symbol, Decimal("0"))
            target_position_value = target_value * target_weight / Decimal("100")
            current_value = holding["value"]
            price = holding["price"]

            if symbol not in index_symbols:
                sells.append({
                    "symbol": symbol,
                    "name": holding["name"],
                    "shares": float(holding["shares"]),
                    "notional": float(current_value),
                    "reason": "Not in S&P 500 index",
                })
                total_sell_value += current_value
            elif current_value > target_position_value:
                excess_value = current_value - target_position_value
                excess_shares = excess_value / price
                if excess_shares > Decimal("0.01"):
                    sells.append({
                        "symbol": symbol,
                        "name": holding["name"],
                        "shares": float(excess_shares.quantize(Decimal("0.0001"))),
                        "notional": float(excess_value),
                        "reason": f"Overweight (target: ${float(target_position_value):,.0f})",
                    })
                    total_sell_value += excess_value

        # Step 2: Calculate buys - underweight positions
        for constituent in constituents:
            symbol = constituent.symbol
            target_position_value = target_value * constituent.weight / Decimal("100")
            current_value = current_holdings.get(symbol, {}).get("value", Decimal("0"))

            if current_value < target_position_value:
                buy_value = target_position_value - current_value

                if symbol in current_holdings:
                    price = current_holdings[symbol]["price"]
                elif alpaca:
                    try:
                        price = alpaca.get_quote(symbol) or Decimal("100")
                    except Exception:
                        price = Decimal("100")
                else:
                    price = Decimal("100")

                shares = buy_value / price
                if shares > Decimal("0.01"):
                    buys.append({
                        "symbol": symbol,
                        "name": name_by_symbol.get(symbol, symbol),
                        "shares": float(shares.quantize(Decimal("0.0001"))),
                        "notional": float(buy_value),
                        "reason": f"Underweight (target: ${float(target_position_value):,.0f})",
                    })
                    total_buy_value += buy_value

        # Add trades to queue
        trades_added = 0

        for sell in sells:
            trade_queue.add_trade(
                trade_type=TradeType.REBALANCE,
                action=TradeAction.SELL,
                symbol=sell["symbol"],
                name=sell["name"],
                shares=Decimal(str(sell["shares"])),
                current_price=current_holdings.get(
                    sell["symbol"], {}
                ).get("price", Decimal("100")),
                reason=sell["reason"],
            )
            trades_added += 1

        for buy in buys:
            price = current_holdings.get(buy["symbol"], {}).get("price")
            if not price and alpaca:
                try:
                    price = alpaca.get_quote(buy["symbol"]) or Decimal("100")
                except Exception:
                    price = Decimal("100")
            if not price:
                price = Decimal("100")

            trade_queue.add_trade(
                trade_type=TradeType.REBALANCE,
                action=TradeAction.BUY,
                symbol=buy["symbol"],
                name=buy["name"],
                shares=Decimal(str(buy["shares"])),
                current_price=price,
                reason=buy["reason"],
            )
            trades_added += 1

        current_value = sum(h["value"] for h in current_holdings.values())
        net_cash_flow = total_sell_value - total_buy_value

        return ToolResult(
            success=True,
            data={
                "target_value": float(target_value),
                "current_value": float(current_value),
                "total_sells": len(sells),
                "total_buys": len(buys),
                "sell_value": float(total_sell_value),
                "buy_value": float(total_buy_value),
                "net_cash_flow": float(net_cash_flow),
                "trades_added": trades_added,
                "sells": sells[:10],
                "buys": buys[:10],
                "message": (
                    f"Added {trades_added} trades to queue: "
                    f"{len(sells)} sells (${float(total_sell_value):,.0f}) and "
                    f"{len(buys)} buys (${float(total_buy_value):,.0f}). "
                    f"Net cash flow: ${float(net_cash_flow):+,.0f}"
                ),
            },
        )
    except Exception as e:
        logger.exception("Error in rebalance_to_target")
        return ToolResult(success=False, data={}, error=str(e))
