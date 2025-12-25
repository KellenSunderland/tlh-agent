"""Configuration management for TLH Agent."""

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


def _decimal_default(obj):
    """JSON encoder for Decimal."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _parse_decimal(value: str | int | float | Decimal) -> Decimal:
    """Parse a value to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class AppConfig:
    """Application configuration."""

    # Alpaca API credentials
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    # Harvest rules
    min_loss_usd: Decimal = field(default_factory=lambda: Decimal("100"))
    min_loss_pct: Decimal = field(default_factory=lambda: Decimal("3.0"))
    min_tax_benefit: Decimal = field(default_factory=lambda: Decimal("50"))
    tax_rate: Decimal = field(default_factory=lambda: Decimal("0.35"))
    min_holding_days: int = 7
    max_harvest_pct: Decimal = field(default_factory=lambda: Decimal("10.0"))
    wash_sale_days: int = 31

    # Paths
    config_dir: Path = field(default_factory=lambda: Path.home() / ".tlh-agent")

    @property
    def config_path(self) -> Path:
        """Path to config file."""
        return self.config_dir / "config.json"

    @property
    def state_path(self) -> Path:
        """Path to state file."""
        return self.config_dir / "state.json"

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "AppConfig":
        """Load configuration from file.

        Args:
            config_dir: Optional config directory override.

        Returns:
            Loaded configuration (or defaults if file doesn't exist).
        """
        if config_dir is None:
            config_dir = Path.home() / ".tlh-agent"

        config_path = config_dir / "config.json"
        config = cls(config_dir=config_dir)

        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                config = cls._from_dict(data, config_dir)

        # Also check environment variables for API keys
        if not config.alpaca_api_key:
            config.alpaca_api_key = os.environ.get("ALPACA_API_KEY", "")
        if not config.alpaca_secret_key:
            config.alpaca_secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

        return config

    @classmethod
    def _from_dict(cls, data: dict, config_dir: Path) -> "AppConfig":
        """Create config from dictionary."""
        return cls(
            alpaca_api_key=data.get("alpaca_api_key", ""),
            alpaca_secret_key=data.get("alpaca_secret_key", ""),
            alpaca_paper=data.get("alpaca_paper", True),
            min_loss_usd=_parse_decimal(data.get("min_loss_usd", "100")),
            min_loss_pct=_parse_decimal(data.get("min_loss_pct", "3.0")),
            min_tax_benefit=_parse_decimal(data.get("min_tax_benefit", "50")),
            tax_rate=_parse_decimal(data.get("tax_rate", "0.35")),
            min_holding_days=data.get("min_holding_days", 7),
            max_harvest_pct=_parse_decimal(data.get("max_harvest_pct", "10.0")),
            wash_sale_days=data.get("wash_sale_days", 31),
            config_dir=config_dir,
        )

    def save(self) -> None:
        """Save configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "alpaca_api_key": self.alpaca_api_key,
            "alpaca_secret_key": self.alpaca_secret_key,
            "alpaca_paper": self.alpaca_paper,
            "min_loss_usd": str(self.min_loss_usd),
            "min_loss_pct": str(self.min_loss_pct),
            "min_tax_benefit": str(self.min_tax_benefit),
            "tax_rate": str(self.tax_rate),
            "min_holding_days": self.min_holding_days,
            "max_harvest_pct": str(self.max_harvest_pct),
            "wash_sale_days": self.wash_sale_days,
        }

        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def has_alpaca_credentials(self) -> bool:
        """Check if Alpaca credentials are configured."""
        return bool(self.alpaca_api_key and self.alpaca_secret_key)
