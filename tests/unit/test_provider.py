"""Tests for service provider."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tlh_agent.services.provider import (
    ServiceProvider,
    get_provider,
    reset_provider,
    set_provider,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / ".tlh-agent"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture(autouse=True)
def reset_global_provider():
    """Reset global provider before and after each test."""
    reset_provider()
    yield
    reset_provider()


class TestServiceProvider:
    """Tests for ServiceProvider."""

    def test_create_mock_mode(self, temp_config_dir: Path) -> None:
        """Test creating provider in mock mode."""
        provider = ServiceProvider.create_mock(config_dir=temp_config_dir)

        assert provider.alpaca is None
        assert provider.portfolio is None
        assert provider.scanner is None
        assert provider.execution is None
        assert provider.is_live is False

    @patch("tlh_agent.config.get_alpaca_credentials")
    def test_create_without_credentials(
        self, mock_get_creds: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test creating provider without Alpaca credentials."""
        mock_get_creds.return_value = None

        provider = ServiceProvider.create(config_dir=temp_config_dir)

        assert provider.alpaca is None
        assert provider.is_live is False

    def test_wash_sale_always_available(self, temp_config_dir: Path) -> None:
        """Test wash sale service is always available."""
        provider = ServiceProvider.create_mock(config_dir=temp_config_dir)

        assert provider.wash_sale is not None
        # Should be functional
        restriction = provider.wash_sale.create_restriction(
            ticker="AAPL",
            shares_sold=Decimal("100"),
            sale_price=Decimal("150"),
        )
        assert restriction.ticker == "AAPL"

    def test_evaluator_always_available(self, temp_config_dir: Path) -> None:
        """Test evaluator is always available."""
        provider = ServiceProvider.create_mock(config_dir=temp_config_dir)

        assert provider.evaluator is not None
        assert provider.rules is not None
        # Check default rules
        assert provider.rules.min_loss_usd == Decimal("100")

    def test_rules_from_config(self, temp_config_dir: Path) -> None:
        """Test rules are created from config."""
        # Create config with custom values
        from tlh_agent.config import AppConfig
        config = AppConfig(
            config_dir=temp_config_dir,
            min_loss_usd=Decimal("200"),
            tax_rate=Decimal("0.40"),
        )
        config.save()

        provider = ServiceProvider.create(config_dir=temp_config_dir)

        assert provider.rules.min_loss_usd == Decimal("200")
        assert provider.rules.tax_rate == Decimal("0.40")

    def test_update_config(self, temp_config_dir: Path) -> None:
        """Test updating config."""
        provider = ServiceProvider.create_mock(config_dir=temp_config_dir)
        original_min = provider.rules.min_loss_usd

        provider.update_config(min_loss_usd=Decimal("500"))

        assert provider.rules.min_loss_usd == Decimal("500")
        assert provider.rules.min_loss_usd != original_min

    def test_get_status(self, temp_config_dir: Path) -> None:
        """Test getting service status."""
        provider = ServiceProvider.create_mock(config_dir=temp_config_dir)

        status = provider.get_status()

        assert status["alpaca_connected"] is False
        assert status["wash_sale_service"] is True
        assert "config_path" in status
        assert "state_path" in status

    @patch("tlh_agent.services.provider.AlpacaClient")
    @patch("tlh_agent.config.get_alpaca_credentials")
    def test_create_with_alpaca(
        self,
        mock_get_creds: MagicMock,
        mock_alpaca_class: MagicMock,
        temp_config_dir: Path,
    ) -> None:
        """Test creating provider with Alpaca connection."""
        # Mock keychain credentials
        mock_get_creds.return_value = ("test-key", "test-secret")

        # Mock Alpaca client
        mock_alpaca = MagicMock()
        mock_alpaca_class.return_value = mock_alpaca

        provider = ServiceProvider.create(config_dir=temp_config_dir)

        assert provider.alpaca is not None
        assert provider.portfolio is not None
        assert provider.scanner is not None
        assert provider.execution is not None
        assert provider.is_live is True


class TestGlobalProvider:
    """Tests for global provider functions."""

    def test_get_provider_creates_if_none(self) -> None:
        """Test get_provider creates provider if none exists."""
        # Mock to avoid actual Alpaca connection
        with patch.object(ServiceProvider, "create") as mock_create:
            mock_provider = MagicMock(spec=ServiceProvider)
            mock_create.return_value = mock_provider

            result = get_provider()

            assert result == mock_provider
            mock_create.assert_called_once()

    def test_get_provider_returns_existing(self) -> None:
        """Test get_provider returns existing provider."""
        mock_provider = MagicMock(spec=ServiceProvider)
        set_provider(mock_provider)

        result = get_provider()

        assert result == mock_provider

    def test_set_provider(self) -> None:
        """Test setting global provider."""
        mock_provider = MagicMock(spec=ServiceProvider)

        set_provider(mock_provider)
        result = get_provider()

        assert result == mock_provider

    def test_reset_provider(self) -> None:
        """Test resetting global provider."""
        mock_provider = MagicMock(spec=ServiceProvider)
        set_provider(mock_provider)

        reset_provider()

        # Should create a new one
        with patch.object(ServiceProvider, "create") as mock_create:
            new_provider = MagicMock(spec=ServiceProvider)
            mock_create.return_value = new_provider

            result = get_provider()

            assert result != mock_provider
