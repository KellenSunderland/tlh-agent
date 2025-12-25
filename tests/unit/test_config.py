"""Tests for configuration module."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tlh_agent.config import AppConfig


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / ".tlh-agent"
    config_dir.mkdir()
    return config_dir


class TestAppConfig:
    """Tests for AppConfig class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = AppConfig()

        assert config.alpaca_api_key == ""
        assert config.alpaca_secret_key == ""
        assert config.alpaca_paper is True
        assert config.min_loss_usd == Decimal("100")
        assert config.min_loss_pct == Decimal("3.0")
        assert config.min_tax_benefit == Decimal("50")
        assert config.tax_rate == Decimal("0.35")
        assert config.min_holding_days == 7
        assert config.max_harvest_pct == Decimal("10.0")
        assert config.wash_sale_days == 31

    def test_has_alpaca_credentials_false(self) -> None:
        """Test has_alpaca_credentials returns False when missing."""
        config = AppConfig()
        assert config.has_alpaca_credentials() is False

    def test_has_alpaca_credentials_true(self) -> None:
        """Test has_alpaca_credentials returns True when set."""
        config = AppConfig(
            alpaca_api_key="test_key",
            alpaca_secret_key="test_secret",
        )
        assert config.has_alpaca_credentials() is True

    def test_load_creates_defaults_when_no_file(self, temp_config_dir: Path) -> None:
        """Test load returns defaults when config file doesn't exist."""
        config = AppConfig.load(temp_config_dir)

        assert config.alpaca_paper is True
        assert config.min_loss_usd == Decimal("100")

    def test_save_and_load(self, temp_config_dir: Path) -> None:
        """Test saving and loading configuration."""
        original = AppConfig(
            alpaca_api_key="my_key",
            alpaca_secret_key="my_secret",
            alpaca_paper=False,
            min_loss_usd=Decimal("200"),
            min_loss_pct=Decimal("5.0"),
            tax_rate=Decimal("0.40"),
            config_dir=temp_config_dir,
        )
        original.save()

        # Verify file was created
        assert original.config_path.exists()

        # Load it back
        loaded = AppConfig.load(temp_config_dir)

        assert loaded.alpaca_api_key == "my_key"
        assert loaded.alpaca_secret_key == "my_secret"
        assert loaded.alpaca_paper is False
        assert loaded.min_loss_usd == Decimal("200")
        assert loaded.min_loss_pct == Decimal("5.0")
        assert loaded.tax_rate == Decimal("0.40")

    def test_load_from_json_file(self, temp_config_dir: Path) -> None:
        """Test loading from an existing JSON file."""
        config_data = {
            "alpaca_api_key": "json_key",
            "alpaca_secret_key": "json_secret",
            "alpaca_paper": True,
            "min_loss_usd": "150",
            "min_holding_days": 14,
        }

        config_path = temp_config_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = AppConfig.load(temp_config_dir)

        assert config.alpaca_api_key == "json_key"
        assert config.alpaca_secret_key == "json_secret"
        assert config.min_loss_usd == Decimal("150")
        assert config.min_holding_days == 14

    def test_config_paths(self, temp_config_dir: Path) -> None:
        """Test config path properties."""
        config = AppConfig(config_dir=temp_config_dir)

        assert config.config_path == temp_config_dir / "config.json"
        assert config.state_path == temp_config_dir / "state.json"

    def test_env_var_override(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables override empty config values."""
        monkeypatch.setenv("ALPACA_API_KEY", "env_key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "env_secret")

        config = AppConfig.load(temp_config_dir)

        assert config.alpaca_api_key == "env_key"
        assert config.alpaca_secret_key == "env_secret"
