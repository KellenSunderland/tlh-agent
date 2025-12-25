"""Wash sale tracking service for TLH Agent."""

from datetime import date, timedelta
from decimal import Decimal

from tlh_agent.data.local_store import LocalStore, WashSaleRestriction


class WashSaleService:
    """Service for tracking wash sale restrictions.

    The IRS wash sale rule prevents claiming a loss on a security
    if you buy a "substantially identical" security within 30 days
    before or after the sale. This creates a 61-day window.

    This service tracks restrictions when securities are sold for
    harvesting and prevents buying them back too soon.
    """

    # 30 days before + sale date + 30 days after = 61 day total window
    WINDOW_DAYS = 30

    def __init__(self, store: LocalStore) -> None:
        """Initialize wash sale service.

        Args:
            store: Local store for persistence.
        """
        self._store = store

    def create_restriction(
        self,
        ticker: str,
        shares_sold: Decimal,
        sale_price: Decimal,
        sale_date: date | None = None,
    ) -> WashSaleRestriction:
        """Create a wash sale restriction after selling a security.

        Args:
            ticker: The stock symbol that was sold.
            shares_sold: Number of shares sold.
            sale_price: Price per share at sale.
            sale_date: Date of sale (defaults to today).

        Returns:
            The created restriction.
        """
        if sale_date is None:
            sale_date = date.today()

        # Restriction ends 30 days after sale (we use 31 to be safe)
        restriction_end = sale_date + timedelta(days=self.WINDOW_DAYS + 1)

        restriction = WashSaleRestriction(
            id=self._store.new_id(),
            ticker=ticker,
            shares_sold=shares_sold,
            sale_price=sale_price,
            sale_date=sale_date,
            restriction_end=restriction_end,
            rebuy_status="pending",
        )

        self._store.add_restriction(restriction)
        return restriction

    def is_restricted(self, ticker: str) -> bool:
        """Check if a ticker is currently under wash sale restriction.

        Args:
            ticker: The stock symbol to check.

        Returns:
            True if the ticker cannot be bought due to wash sale rules.
        """
        restriction = self._store.get_restriction_by_ticker(ticker)
        return restriction is not None and restriction.is_active

    def get_restriction(self, ticker: str) -> WashSaleRestriction | None:
        """Get the active restriction for a ticker.

        Args:
            ticker: The stock symbol.

        Returns:
            The active restriction, or None if not restricted.
        """
        return self._store.get_restriction_by_ticker(ticker)

    def get_active_restrictions(self) -> list[WashSaleRestriction]:
        """Get all active wash sale restrictions.

        Returns:
            List of active restrictions sorted by restriction end date.
        """
        restrictions = self._store.get_active_restrictions()
        return sorted(restrictions, key=lambda r: r.restriction_end)

    def get_pending_rebuys(self) -> list[WashSaleRestriction]:
        """Get restrictions that are ready for rebuy.

        These are restrictions where:
        - The restriction period has ended
        - The rebuy hasn't been completed yet

        Returns:
            List of restrictions pending rebuy.
        """
        all_restrictions = self._store.get_restrictions()
        return [r for r in all_restrictions if not r.is_active and r.rebuy_status == "pending"]

    def get_clear_date(self, ticker: str) -> date | None:
        """Get the date when a ticker will be clear for rebuy.

        Args:
            ticker: The stock symbol.

        Returns:
            The date when restriction ends, or None if not restricted.
        """
        restriction = self._store.get_restriction_by_ticker(ticker)
        if restriction and restriction.is_active:
            return restriction.restriction_end
        return None

    def days_until_clear(self, ticker: str) -> int | None:
        """Get days until a ticker is clear for rebuy.

        Args:
            ticker: The stock symbol.

        Returns:
            Days remaining, or None if not restricted.
        """
        restriction = self._store.get_restriction_by_ticker(ticker)
        if restriction and restriction.is_active:
            return restriction.days_remaining
        return None

    def mark_rebuy_complete(
        self,
        restriction_id: str,
        rebuy_price: Decimal,
        rebuy_date: date | None = None,
    ) -> None:
        """Mark a restriction as having completed the rebuy.

        Args:
            restriction_id: The restriction ID.
            rebuy_price: Price per share of the rebuy.
            rebuy_date: Date of rebuy (defaults to today).
        """
        restrictions = self._store.get_restrictions()
        for r in restrictions:
            if r.id == restriction_id:
                r.rebuy_status = "completed"
                r.rebuy_price = rebuy_price
                r.rebuy_date = rebuy_date or date.today()
                self._store.update_restriction(r)
                return
        raise ValueError(f"Restriction not found: {restriction_id}")

    def mark_rebuy_skipped(self, restriction_id: str) -> None:
        """Mark a restriction as having skipped the rebuy.

        Used when the user decides not to rebuy the security.

        Args:
            restriction_id: The restriction ID.
        """
        restrictions = self._store.get_restrictions()
        for r in restrictions:
            if r.id == restriction_id:
                r.rebuy_status = "skipped"
                self._store.update_restriction(r)
                return
        raise ValueError(f"Restriction not found: {restriction_id}")

    def would_violate(self, ticker: str, buy_date: date | None = None) -> bool:
        """Check if buying a ticker on a date would violate wash sale rules.

        This checks if there was a sale within 30 days before the buy date.

        Args:
            ticker: The stock symbol.
            buy_date: The proposed buy date (defaults to today).

        Returns:
            True if buying would trigger a wash sale.
        """
        if buy_date is None:
            buy_date = date.today()

        # Check if there's any active restriction for this ticker
        # that would be violated by buying on this date
        all_restrictions = self._store.get_restrictions()

        for r in all_restrictions:
            if r.ticker != ticker:
                continue

            # The wash sale window is 30 days before and after the sale
            window_start = r.sale_date - timedelta(days=self.WINDOW_DAYS)
            window_end = r.sale_date + timedelta(days=self.WINDOW_DAYS)

            if window_start <= buy_date <= window_end:
                return True

        return False

    def cleanup_old_restrictions(self, days_old: int = 90) -> int:
        """Remove restrictions that are completed/skipped and old.

        Args:
            days_old: Remove restrictions older than this many days.

        Returns:
            Number of restrictions removed.
        """
        cutoff = date.today() - timedelta(days=days_old)
        removed = 0

        for r in self._store.get_restrictions():
            if r.rebuy_status in ("completed", "skipped") and r.sale_date < cutoff:
                self._store.remove_restriction(r.id)
                removed += 1

        return removed
