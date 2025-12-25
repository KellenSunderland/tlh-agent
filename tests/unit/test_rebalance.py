"""Tests for tax-aware rebalancing service."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from tlh_agent.services.index import IndexService, TargetAllocation
from tlh_agent.services.portfolio import PortfolioService, Position
from tlh_agent.services.rebalance import (
    RebalancePlan,
    RebalanceRecommendation,
    RebalanceService,
    TradeAction,
)
from tlh_agent.services.wash_sale import WashSaleService


class TestTradeAction:
    """Tests for TradeAction enum."""

    def test_buy_action(self) -> None:
        """Test buy action value."""
        assert TradeAction.BUY.value == "buy"

    def test_sell_action(self) -> None:
        """Test sell action value."""
        assert TradeAction.SELL.value == "sell"


class TestRebalanceRecommendation:
    """Tests for RebalanceRecommendation dataclass."""

    def test_create_buy_recommendation(self) -> None:
        """Test creating a buy recommendation."""
        rec = RebalanceRecommendation(
            symbol="AAPL",
            name="Apple Inc.",
            action=TradeAction.BUY,
            shares=Decimal("10"),
            notional=Decimal("1500"),
            reason="Underweight by 5%",
            tax_impact=None,
            wash_sale_blocked=False,
            current_price=Decimal("150"),
            priority=100,
        )

        assert rec.symbol == "AAPL"
        assert rec.action == TradeAction.BUY
        assert rec.notional == Decimal("1500")
        assert rec.tax_impact is None

    def test_create_sell_recommendation(self) -> None:
        """Test creating a sell recommendation."""
        rec = RebalanceRecommendation(
            symbol="MSFT",
            name="Microsoft",
            action=TradeAction.SELL,
            shares=Decimal("5"),
            notional=Decimal("2000"),
            reason="Harvest loss",
            tax_impact=Decimal("-175"),  # Tax savings
            wash_sale_blocked=False,
            current_price=Decimal("400"),
            priority=-500,
        )

        assert rec.action == TradeAction.SELL
        assert rec.tax_impact == Decimal("-175")


class TestRebalancePlan:
    """Tests for RebalancePlan dataclass."""

    def test_create_plan(self) -> None:
        """Test creating a rebalance plan."""
        plan = RebalancePlan(
            recommendations=[],
            total_buys=Decimal("5000"),
            total_sells=Decimal("3000"),
            net_cash_flow=Decimal("-2000"),
            estimated_tax_savings=Decimal("500"),
            blocked_trades=1,
        )

        assert plan.total_buys == Decimal("5000")
        assert plan.net_cash_flow == Decimal("-2000")
        assert plan.blocked_trades == 1


class TestRebalanceService:
    """Tests for RebalanceService."""

    @pytest.fixture
    def mock_portfolio(self) -> MagicMock:
        """Create a mock portfolio service."""
        mock = MagicMock(spec=PortfolioService)
        mock.get_total_value.return_value = Decimal("100000")
        return mock

    @pytest.fixture
    def mock_index(self) -> MagicMock:
        """Create a mock index service."""
        return MagicMock(spec=IndexService)

    @pytest.fixture
    def mock_wash_sale(self) -> MagicMock:
        """Create a mock wash sale service."""
        mock = MagicMock(spec=WashSaleService)
        mock.get_clear_date.return_value = None  # No restrictions by default
        return mock

    @pytest.fixture
    def service(
        self,
        mock_portfolio: MagicMock,
        mock_index: MagicMock,
        mock_wash_sale: MagicMock,
    ) -> RebalanceService:
        """Create a RebalanceService instance."""
        return RebalanceService(
            portfolio_service=mock_portfolio,
            index_service=mock_index,
            wash_sale_service=mock_wash_sale,
            tax_rate=Decimal("0.35"),
        )

    def test_init(self, service: RebalanceService) -> None:
        """Test service initialization."""
        assert service._tax_rate == Decimal("0.35")

    def test_generate_rebalance_plan_empty(
        self, service: RebalanceService, mock_portfolio: MagicMock, mock_index: MagicMock
    ) -> None:
        """Test generating plan with no positions."""
        mock_portfolio.get_positions.return_value = []
        mock_index.calculate_target_allocations.return_value = []

        plan = service.generate_rebalance_plan()

        assert plan.recommendations == []
        assert plan.total_buys == Decimal("0")
        assert plan.total_sells == Decimal("0")

    def test_generate_rebalance_plan_with_buys(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test generating plan with buy recommendations."""
        mock_portfolio.get_positions.return_value = []

        # Need to buy AAPL
        allocations = [
            TargetAllocation(
                symbol="AAPL",
                name="Apple",
                target_weight=Decimal("10"),
                target_value=Decimal("10000"),
                current_value=Decimal("0"),
                difference=Decimal("10000"),
                difference_pct=Decimal("100"),  # 100% difference
            ),
        ]

        plan = service.generate_rebalance_plan(target_allocations=allocations)

        assert len(plan.recommendations) == 1
        assert plan.recommendations[0].action == TradeAction.BUY
        assert plan.recommendations[0].symbol == "AAPL"
        assert plan.total_buys == Decimal("10000")

    def test_generate_rebalance_plan_with_sells(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test generating plan with sell recommendations."""
        # Have AAPL position
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("140"),  # At a loss
                market_value=Decimal("14000"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("-1000"),  # Loss
                unrealized_gain_loss_pct=Decimal("-6.67"),
            ),
        ]

        # Need to sell some AAPL
        allocations = [
            TargetAllocation(
                symbol="AAPL",
                name="Apple",
                target_weight=Decimal("10"),
                target_value=Decimal("10000"),
                current_value=Decimal("14000"),
                difference=Decimal("-4000"),  # Need to sell
                difference_pct=Decimal("-40"),  # 40% overweight
            ),
        ]

        plan = service.generate_rebalance_plan(target_allocations=allocations)

        assert len(plan.recommendations) == 1
        assert plan.recommendations[0].action == TradeAction.SELL
        assert plan.recommendations[0].symbol == "AAPL"
        assert plan.total_sells > 0

    def test_generate_rebalance_plan_threshold_filtering(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test that small differences are filtered by threshold."""
        mock_portfolio.get_positions.return_value = []

        allocations = [
            TargetAllocation(
                symbol="AAPL",
                name="Apple",
                target_weight=Decimal("10"),
                target_value=Decimal("10000"),
                current_value=Decimal("9950"),  # Only 0.5% off
                difference=Decimal("50"),
                difference_pct=Decimal("0.5"),
            ),
        ]

        plan = service.generate_rebalance_plan(
            target_allocations=allocations,
            threshold_pct=Decimal("1.0"),  # 1% threshold
        )

        # Should be filtered out
        assert len(plan.recommendations) == 0

    def test_generate_rebalance_plan_max_trades(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test max trades limit."""
        mock_portfolio.get_positions.return_value = []

        allocations = [
            TargetAllocation(
                symbol=f"SYM{i}",
                name=f"Stock {i}",
                target_weight=Decimal("5"),
                target_value=Decimal("5000"),
                current_value=Decimal("0"),
                difference=Decimal("5000"),
                difference_pct=Decimal("100"),
            )
            for i in range(10)
        ]

        plan = service.generate_rebalance_plan(
            target_allocations=allocations,
            max_trades=3,
        )

        assert len(plan.recommendations) == 3

    def test_get_harvest_opportunities(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test getting tax-loss harvest opportunities."""
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("140"),
                market_value=Decimal("14000"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("-1000"),  # Loss
                unrealized_gain_loss_pct=Decimal("-6.67"),
            ),
            Position(
                ticker="MSFT",
                name="Microsoft",
                shares=Decimal("50"),
                avg_cost_per_share=Decimal("300"),
                current_price=Decimal("350"),
                market_value=Decimal("17500"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("2500"),  # Gain
                unrealized_gain_loss_pct=Decimal("16.67"),
            ),
        ]

        opportunities = service.get_harvest_opportunities(min_loss=Decimal("100"))

        # Only AAPL has a loss
        assert len(opportunities) == 1
        assert opportunities[0].symbol == "AAPL"
        assert opportunities[0].action == TradeAction.SELL

    def test_get_harvest_opportunities_min_loss_filter(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test that small losses are filtered."""
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("10"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("149"),
                market_value=Decimal("1490"),
                cost_basis=Decimal("1500"),
                unrealized_gain_loss=Decimal("-10"),  # Small loss
                unrealized_gain_loss_pct=Decimal("-0.67"),
            ),
        ]

        opportunities = service.get_harvest_opportunities(min_loss=Decimal("100"))

        # Should be filtered out
        assert len(opportunities) == 0

    def test_get_harvest_opportunities_wash_sale_blocked(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test that wash sale restrictions are flagged."""
        future_date = date.today() + timedelta(days=15)
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("140"),
                market_value=Decimal("14000"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("-1000"),
                unrealized_gain_loss_pct=Decimal("-6.67"),
                wash_sale_until=future_date,  # Under restriction
            ),
        ]

        opportunities = service.get_harvest_opportunities()

        assert len(opportunities) == 1
        assert opportunities[0].wash_sale_blocked is True

    def test_estimate_annual_tax_savings(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test estimating annual tax savings."""
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("140"),
                market_value=Decimal("14000"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("-1000"),
                unrealized_gain_loss_pct=Decimal("-6.67"),
            ),
            Position(
                ticker="MSFT",
                name="Microsoft",
                shares=Decimal("50"),
                avg_cost_per_share=Decimal("400"),
                current_price=Decimal("380"),
                market_value=Decimal("19000"),
                cost_basis=Decimal("20000"),
                unrealized_gain_loss=Decimal("-1000"),
                unrealized_gain_loss_pct=Decimal("-5.0"),
            ),
        ]

        savings = service.estimate_annual_tax_savings()

        # -1000 * 0.35 = -350 per position, total = 700
        assert savings == Decimal("700")

    def test_buy_blocked_by_wash_sale(
        self,
        service: RebalanceService,
        mock_portfolio: MagicMock,
        mock_wash_sale: MagicMock,
    ) -> None:
        """Test that buys are blocked when under wash sale restriction."""
        mock_portfolio.get_positions.return_value = []

        # Simulate wash sale restriction on AAPL
        mock_wash_sale.get_clear_date.return_value = date.today() + timedelta(days=10)

        allocations = [
            TargetAllocation(
                symbol="AAPL",
                name="Apple",
                target_weight=Decimal("10"),
                target_value=Decimal("10000"),
                current_value=Decimal("0"),
                difference=Decimal("10000"),
                difference_pct=Decimal("100"),
            ),
        ]

        plan = service.generate_rebalance_plan(target_allocations=allocations)

        assert len(plan.recommendations) == 1
        assert plan.recommendations[0].wash_sale_blocked is True
        assert plan.blocked_trades == 1

    def test_sell_prioritizes_losses(
        self, service: RebalanceService, mock_portfolio: MagicMock
    ) -> None:
        """Test that sells prioritize positions with larger losses."""
        mock_portfolio.get_positions.return_value = [
            Position(
                ticker="AAPL",
                name="Apple",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("150"),
                current_price=Decimal("140"),
                market_value=Decimal("14000"),
                cost_basis=Decimal("15000"),
                unrealized_gain_loss=Decimal("-1000"),  # Small loss
                unrealized_gain_loss_pct=Decimal("-6.67"),
            ),
            Position(
                ticker="MSFT",
                name="Microsoft",
                shares=Decimal("100"),
                avg_cost_per_share=Decimal("400"),
                current_price=Decimal("350"),
                market_value=Decimal("35000"),
                cost_basis=Decimal("40000"),
                unrealized_gain_loss=Decimal("-5000"),  # Big loss
                unrealized_gain_loss_pct=Decimal("-12.5"),
            ),
        ]

        allocations = [
            TargetAllocation(
                symbol="AAPL",
                name="Apple",
                target_weight=Decimal("5"),
                target_value=Decimal("5000"),
                current_value=Decimal("14000"),
                difference=Decimal("-9000"),
                difference_pct=Decimal("-180"),
            ),
            TargetAllocation(
                symbol="MSFT",
                name="Microsoft",
                target_weight=Decimal("20"),
                target_value=Decimal("20000"),
                current_value=Decimal("35000"),
                difference=Decimal("-15000"),
                difference_pct=Decimal("-75"),
            ),
        ]

        plan = service.generate_rebalance_plan(target_allocations=allocations)

        assert len(plan.recommendations) == 2
        # MSFT should be first (larger loss = higher priority)
        assert plan.recommendations[0].symbol == "MSFT"
        assert plan.recommendations[1].symbol == "AAPL"
