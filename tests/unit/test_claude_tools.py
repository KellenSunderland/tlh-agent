"""Tests for Claude tool provider."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from tlh_agent.services.claude_tools import ClaudeToolProvider, ToolName, ToolResult
from tlh_agent.services.index import IndexConstituent, IndexService
from tlh_agent.services.portfolio import PortfolioService, Position
from tlh_agent.services.rebalance import (
    RebalancePlan,
    RebalanceRecommendation,
    RebalanceService,
    TradeAction,
)
from tlh_agent.services.scanner import HarvestOpportunity, PortfolioScanner, ScanResult
from tlh_agent.services.trade_queue import (
    TradeAction as QueueTradeAction,
)
from tlh_agent.services.trade_queue import (
    TradeQueueService,
    TradeType,
)


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result serialization."""
        result = ToolResult(success=True, data={"key": "value"})

        assert result.success is True
        assert result.error is None
        assert '"key": "value"' in result.to_json()

    def test_error_result(self) -> None:
        """Test error result serialization."""
        result = ToolResult(success=False, data={}, error="Something went wrong")

        assert result.success is False
        assert '"error": "Something went wrong"' in result.to_json()

    def test_decimal_serialization(self) -> None:
        """Test that Decimal values are serialized correctly."""
        result = ToolResult(success=True, data={"amount": Decimal("123.45")})

        json_str = result.to_json()
        assert "123.45" in json_str


class TestClaudeToolProvider:
    """Tests for ClaudeToolProvider."""

    @pytest.fixture
    def mock_portfolio_service(self) -> MagicMock:
        """Create a mock portfolio service."""
        service = MagicMock(spec=PortfolioService)
        position = Position(
            ticker="AAPL",
            name="Apple Inc.",
            shares=Decimal("100"),
            avg_cost_per_share=Decimal("140"),
            current_price=Decimal("150"),
            market_value=Decimal("15000"),
            cost_basis=Decimal("14000"),
            unrealized_gain_loss=Decimal("1000"),
            unrealized_gain_loss_pct=Decimal("7.14"),
        )
        service.get_positions.return_value = [position]
        return service

    @pytest.fixture
    def mock_scanner(self) -> MagicMock:
        """Create a mock scanner."""
        scanner = MagicMock(spec=PortfolioScanner)
        opportunity = HarvestOpportunity(
            ticker="GOOGL",
            shares=Decimal("50"),
            current_price=Decimal("140"),
            avg_cost=Decimal("160"),
            market_value=Decimal("7000"),
            cost_basis=Decimal("8000"),
            unrealized_loss=Decimal("1000"),
            loss_pct=Decimal("-12.5"),
            estimated_tax_benefit=Decimal("350"),
            days_held=45,
        )
        scan_result = ScanResult(
            opportunities=[opportunity],
            total_potential_benefit=Decimal("350"),
            positions_scanned=10,
            positions_with_loss=1,
            positions_restricted=0,
        )
        scanner.scan.return_value = scan_result
        return scanner

    @pytest.fixture
    def mock_index_service(self) -> MagicMock:
        """Create a mock index service."""
        service = MagicMock(spec=IndexService)
        service.get_constituents.return_value = [
            IndexConstituent(
                symbol="AAPL",
                name="Apple Inc.",
                weight=Decimal("7.0"),
                sector="Technology",
            ),
            IndexConstituent(
                symbol="MSFT",
                name="Microsoft",
                weight=Decimal("6.5"),
                sector="Technology",
            ),
        ]
        return service

    @pytest.fixture
    def mock_rebalance_service(self) -> MagicMock:
        """Create a mock rebalance service."""
        service = MagicMock(spec=RebalanceService)
        service.generate_rebalance_plan.return_value = RebalancePlan(
            recommendations=[
                RebalanceRecommendation(
                    symbol="AAPL",
                    name="Apple Inc.",
                    action=TradeAction.BUY,
                    shares=Decimal("10"),
                    notional=Decimal("1500"),
                    reason="Underweight",
                    tax_impact=None,
                    wash_sale_blocked=False,
                    current_price=Decimal("150"),
                    priority=100,
                ),
            ],
            total_buys=Decimal("1500"),
            total_sells=Decimal("0"),
            net_cash_flow=Decimal("-1500"),
            estimated_tax_savings=Decimal("0"),
            blocked_trades=0,
        )
        return service

    @pytest.fixture
    def provider(self, mock_portfolio_service: MagicMock) -> ClaudeToolProvider:
        """Create a tool provider with mocked services."""
        return ClaudeToolProvider(portfolio_service=mock_portfolio_service)

    def test_get_tool_definitions(self, provider: ClaudeToolProvider) -> None:
        """Test getting tool definitions."""
        definitions = provider.get_tool_definitions()

        assert len(definitions) == 6
        names = [d.name for d in definitions]
        assert ToolName.GET_PORTFOLIO_SUMMARY.value in names
        assert ToolName.GET_POSITIONS.value in names
        assert ToolName.GET_HARVEST_OPPORTUNITIES.value in names
        assert ToolName.GET_INDEX_ALLOCATION.value in names
        assert ToolName.GET_REBALANCE_PLAN.value in names
        assert ToolName.PROPOSE_TRADES.value in names

    def test_get_portfolio_summary(
        self,
        mock_portfolio_service: MagicMock,
        mock_scanner: MagicMock,
    ) -> None:
        """Test getting portfolio summary."""
        provider = ClaudeToolProvider(
            portfolio_service=mock_portfolio_service,
            scanner=mock_scanner,
        )
        result = provider.execute_tool(ToolName.GET_PORTFOLIO_SUMMARY.value, {})

        assert result.success is True
        assert "total_value" in result.data
        assert result.data["total_value"] == 15000.0
        assert result.data["position_count"] == 1
        assert result.data["harvest_opportunities"] == 1

    def test_get_portfolio_summary_no_service(self) -> None:
        """Test portfolio summary without portfolio service."""
        provider = ClaudeToolProvider()
        result = provider.execute_tool(ToolName.GET_PORTFOLIO_SUMMARY.value, {})

        assert result.success is False
        assert "not available" in result.error

    def test_get_positions(self, provider: ClaudeToolProvider) -> None:
        """Test getting positions."""
        result = provider.execute_tool(ToolName.GET_POSITIONS.value, {})

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "AAPL"
        assert result.data[0]["market_value"] == 15000.0

    def test_get_positions_with_sort(self, provider: ClaudeToolProvider) -> None:
        """Test getting positions with sorting."""
        result = provider.execute_tool(
            ToolName.GET_POSITIONS.value,
            {"sort_by": "symbol"},
        )

        assert result.success is True

    def test_get_positions_with_limit(self, provider: ClaudeToolProvider) -> None:
        """Test getting positions with limit."""
        result = provider.execute_tool(
            ToolName.GET_POSITIONS.value,
            {"limit": 1},
        )

        assert result.success is True
        assert len(result.data) == 1

    def test_get_harvest_opportunities(self, mock_scanner: MagicMock) -> None:
        """Test getting harvest opportunities."""
        provider = ClaudeToolProvider(scanner=mock_scanner)
        result = provider.execute_tool(ToolName.GET_HARVEST_OPPORTUNITIES.value, {})

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "GOOGL"
        assert result.data[0]["unrealized_loss"] == 1000.0
        assert result.data[0]["estimated_tax_benefit"] == 350.0

    def test_get_harvest_opportunities_with_min_loss(
        self, mock_scanner: MagicMock
    ) -> None:
        """Test filtering harvest opportunities by minimum loss."""
        provider = ClaudeToolProvider(scanner=mock_scanner)
        result = provider.execute_tool(
            ToolName.GET_HARVEST_OPPORTUNITIES.value,
            {"min_loss": 2000},
        )

        assert result.success is True
        assert len(result.data) == 0  # No opportunities above $2000

    def test_get_index_allocation(
        self,
        mock_portfolio_service: MagicMock,
        mock_index_service: MagicMock,
    ) -> None:
        """Test getting index allocation."""
        provider = ClaudeToolProvider(
            portfolio_service=mock_portfolio_service,
            index_service=mock_index_service,
        )

        result = provider.execute_tool(ToolName.GET_INDEX_ALLOCATION.value, {})

        assert result.success is True
        assert "portfolio_value" in result.data
        assert "allocations" in result.data

    def test_get_index_allocation_no_service(
        self, mock_portfolio_service: MagicMock
    ) -> None:
        """Test index allocation without index service."""
        provider = ClaudeToolProvider(portfolio_service=mock_portfolio_service)

        result = provider.execute_tool(ToolName.GET_INDEX_ALLOCATION.value, {})

        assert result.success is False
        assert "not available" in result.error

    def test_get_rebalance_plan(
        self,
        mock_rebalance_service: MagicMock,
    ) -> None:
        """Test getting rebalance plan."""
        provider = ClaudeToolProvider(rebalance_service=mock_rebalance_service)

        result = provider.execute_tool(ToolName.GET_REBALANCE_PLAN.value, {})

        assert result.success is True
        assert "recommendations" in result.data
        assert len(result.data["recommendations"]) == 1
        assert result.data["total_buys"] == 1500.0
        assert result.data["net_cash_flow"] == -1500.0
        assert result.data["blocked_trades"] == 0
        rec = result.data["recommendations"][0]
        assert rec["symbol"] == "AAPL"
        assert rec["action"] == "buy"

    def test_get_rebalance_plan_no_service(self) -> None:
        """Test rebalance plan without service."""
        provider = ClaudeToolProvider()

        result = provider.execute_tool(ToolName.GET_REBALANCE_PLAN.value, {})

        assert result.success is False
        assert "not available" in result.error

    def test_propose_trades(self) -> None:
        """Test proposing trades."""
        trade_queue = TradeQueueService()
        provider = ClaudeToolProvider(trade_queue=trade_queue)

        result = provider.execute_tool(
            ToolName.PROPOSE_TRADES.value,
            {
                "trades": [
                    {
                        "symbol": "AAPL",
                        "action": "buy",
                        "shares": 10,
                        "reason": "Underweight",
                    },
                    {
                        "symbol": "GOOGL",
                        "action": "sell",
                        "shares": 5,
                        "reason": "Tax loss harvest",
                    },
                ],
                "trade_type": "rebalance",
            },
        )

        assert result.success is True
        assert result.data["trades_added"] == 2
        assert len(trade_queue.get_all_trades()) == 2

    def test_propose_trades_harvest_type(self) -> None:
        """Test proposing harvest trades."""
        trade_queue = TradeQueueService()
        provider = ClaudeToolProvider(trade_queue=trade_queue)

        result = provider.execute_tool(
            ToolName.PROPOSE_TRADES.value,
            {
                "trades": [
                    {
                        "symbol": "GOOGL",
                        "action": "sell",
                        "shares": 50,
                        "reason": "Tax loss harvest",
                    },
                ],
                "trade_type": "harvest",
            },
        )

        assert result.success is True
        trades = trade_queue.get_all_trades()
        assert len(trades) == 1
        assert trades[0].trade_type == TradeType.HARVEST
        assert trades[0].action == QueueTradeAction.SELL

    def test_propose_trades_index_buy_type(self) -> None:
        """Test proposing index buy trades."""
        trade_queue = TradeQueueService()
        provider = ClaudeToolProvider(trade_queue=trade_queue)

        result = provider.execute_tool(
            ToolName.PROPOSE_TRADES.value,
            {
                "trades": [
                    {
                        "symbol": "AAPL",
                        "action": "buy",
                        "shares": 100,
                        "reason": "Track S&P 500",
                    },
                ],
                "trade_type": "index_buy",
            },
        )

        assert result.success is True
        trades = trade_queue.get_all_trades()
        assert len(trades) == 1
        assert trades[0].trade_type == TradeType.INDEX_BUY
        assert trades[0].action == QueueTradeAction.BUY

    def test_unknown_tool(self, provider: ClaudeToolProvider) -> None:
        """Test executing unknown tool."""
        result = provider.execute_tool("unknown_tool", {})

        assert result.success is False
        assert "Unknown tool" in result.error
