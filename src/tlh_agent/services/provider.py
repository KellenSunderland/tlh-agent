"""Service provider for TLH Agent.

Manages service instances and provides dependency injection.
"""

from dataclasses import dataclass
from pathlib import Path

from tlh_agent.brokers.alpaca import AlpacaClient
from tlh_agent.config import AppConfig
from tlh_agent.data.local_store import LocalStore
from tlh_agent.services.execution import HarvestExecutionService
from tlh_agent.services.portfolio import PortfolioService
from tlh_agent.services.rules import HarvestEvaluator, HarvestRules
from tlh_agent.services.scanner import PortfolioScanner
from tlh_agent.services.wash_sale import WashSaleService


@dataclass
class ServiceProvider:
    """Container for all TLH Agent services.

    Creates and manages service instances with proper dependency injection.
    Services can use live Alpaca data or fall back to mock mode.
    """

    config: AppConfig
    store: LocalStore
    alpaca: AlpacaClient | None
    wash_sale: WashSaleService
    portfolio: PortfolioService | None
    scanner: PortfolioScanner | None
    execution: HarvestExecutionService | None
    evaluator: HarvestEvaluator

    @property
    def is_live(self) -> bool:
        """Whether services are connected to live Alpaca."""
        return self.alpaca is not None

    @property
    def rules(self) -> HarvestRules:
        """Get current harvest rules."""
        return self.evaluator.rules

    @classmethod
    def create(
        cls,
        config_dir: Path | None = None,
        connect_alpaca: bool = True,
    ) -> "ServiceProvider":
        """Create a service provider with all services.

        Args:
            config_dir: Optional config directory override.
            connect_alpaca: Whether to connect to Alpaca (False for mock mode).

        Returns:
            Configured ServiceProvider instance.
        """
        # Load configuration
        config = AppConfig.load(config_dir)
        store = LocalStore(config.state_path)

        # Create rules from config
        rules = HarvestRules(
            min_loss_usd=config.min_loss_usd,
            min_loss_pct=config.min_loss_pct,
            min_tax_benefit=config.min_tax_benefit,
            tax_rate=config.tax_rate,
            min_holding_days=config.min_holding_days,
            max_harvest_pct=config.max_harvest_pct,
            wash_sale_days=config.wash_sale_days,
        )
        evaluator = HarvestEvaluator(rules)

        # Create wash sale service (works without Alpaca)
        wash_sale = WashSaleService(store)

        # Try to connect to Alpaca if credentials available
        alpaca: AlpacaClient | None = None
        portfolio: PortfolioService | None = None
        scanner: PortfolioScanner | None = None
        execution: HarvestExecutionService | None = None

        if connect_alpaca and config.has_alpaca_credentials():
            try:
                alpaca = AlpacaClient(
                    api_key=config.alpaca_api_key,
                    secret_key=config.alpaca_secret_key,
                    paper=config.alpaca_paper,
                )

                # Create services that depend on Alpaca
                portfolio = PortfolioService(alpaca, store, wash_sale)
                scanner = PortfolioScanner(portfolio, wash_sale, store, rules)
                execution = HarvestExecutionService(alpaca, store, wash_sale)

            except Exception:
                # Failed to connect - services will be None
                pass

        return cls(
            config=config,
            store=store,
            alpaca=alpaca,
            wash_sale=wash_sale,
            portfolio=portfolio,
            scanner=scanner,
            execution=execution,
            evaluator=evaluator,
        )

    @classmethod
    def create_mock(cls, config_dir: Path | None = None) -> "ServiceProvider":
        """Create a service provider without Alpaca connection.

        Useful for testing or when Alpaca credentials aren't configured.

        Args:
            config_dir: Optional config directory override.

        Returns:
            ServiceProvider in mock mode.
        """
        return cls.create(config_dir=config_dir, connect_alpaca=False)

    def update_config(self, **kwargs) -> None:
        """Update configuration and re-create affected services.

        Args:
            **kwargs: Config fields to update.
        """
        # Update config
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # Save updated config
        self.config.save()

        # Update rules if relevant fields changed
        rule_fields = {
            "min_loss_usd", "min_loss_pct", "min_tax_benefit",
            "tax_rate", "min_holding_days", "max_harvest_pct", "wash_sale_days"
        }

        if any(k in rule_fields for k in kwargs):
            rules = HarvestRules(
                min_loss_usd=self.config.min_loss_usd,
                min_loss_pct=self.config.min_loss_pct,
                min_tax_benefit=self.config.min_tax_benefit,
                tax_rate=self.config.tax_rate,
                min_holding_days=self.config.min_holding_days,
                max_harvest_pct=self.config.max_harvest_pct,
                wash_sale_days=self.config.wash_sale_days,
            )
            self.evaluator = HarvestEvaluator(rules)

            # Update scanner rules if available
            if self.scanner:
                self.scanner.update_rules(rules)

    def get_status(self) -> dict:
        """Get status of all services.

        Returns:
            Dict with service status information.
        """
        return {
            "alpaca_connected": self.alpaca is not None,
            "alpaca_paper": self.config.alpaca_paper,
            "portfolio_service": self.portfolio is not None,
            "scanner_service": self.scanner is not None,
            "execution_service": self.execution is not None,
            "wash_sale_service": True,  # Always available
            "config_path": str(self.config.config_path),
            "state_path": str(self.config.state_path),
        }


# Global service provider instance (optional singleton pattern)
_provider: ServiceProvider | None = None


def get_provider() -> ServiceProvider:
    """Get the global service provider instance.

    Creates one if it doesn't exist.

    Returns:
        The global ServiceProvider instance.
    """
    global _provider
    if _provider is None:
        _provider = ServiceProvider.create()
    return _provider


def set_provider(provider: ServiceProvider) -> None:
    """Set the global service provider instance.

    Args:
        provider: The provider to use globally.
    """
    global _provider
    _provider = provider


def reset_provider() -> None:
    """Reset the global service provider."""
    global _provider
    _provider = None
