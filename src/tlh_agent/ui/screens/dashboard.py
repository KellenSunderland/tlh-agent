"""Dashboard screen with portfolio summary and key metrics."""

import tkinter as tk

from tlh_agent.data.mock_data import MockDataFactory
from tlh_agent.services import get_provider
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card, MetricCard
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class DashboardScreen(BaseScreen):
    """Main dashboard showing portfolio overview and harvest opportunities."""

    def _setup_ui(self) -> None:
        """Set up the dashboard layout."""
        # Header
        header = PageHeader(
            self, title="Dashboard", subtitle="Portfolio overview and harvest opportunities"
        )
        header.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Summary cards row - use grid for equal width columns
        cards_frame = tk.Frame(self, bg=Colors.BG_PRIMARY)
        cards_frame.pack(fill=tk.X, pady=(0, Spacing.LG))

        self.cards: dict[str, MetricCard] = {}

        card_configs = [
            ("total_value", "Total Value", "$0.00", None),
            ("unrealized", "Unrealized G/L", "$0.00", None),
            ("ytd_harvested", "YTD Harvested", "$0.00", None),
            ("pending", "Pending Harvests", "0", None),
        ]

        for i, (card_id, label, value, trend) in enumerate(card_configs):
            card = MetricCard(cards_frame, label=label, value=value, trend=trend)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else Spacing.SM, 0))
            cards_frame.grid_columnconfigure(i, weight=1, uniform="cards")
            self.cards[card_id] = card

        # Top Harvest Opportunities section
        self.opps_card = Card(self, title="Top Harvest Opportunities")
        self.opps_card.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Add "View All" link to header (styled as clickable text)
        view_all_btn = tk.Label(
            self.opps_card._header,
            text="View All →",
            font=Fonts.BODY,
            fg=Colors.ACCENT,
            bg=Colors.BG_SECONDARY,
            cursor="hand2",
        )
        view_all_btn.pack(side=tk.RIGHT, padx=Spacing.SM)
        view_all_btn.bind("<Button-1>", lambda e: self._on_view_all_opportunities())
        view_all_btn.bind("<Enter>", lambda e: view_all_btn.configure(fg=Colors.ACCENT_HOVER))
        view_all_btn.bind("<Leave>", lambda e: view_all_btn.configure(fg=Colors.ACCENT))

        # Store reference to content frame
        self.opps_content = self.opps_card.content

        # Wash Sale Alerts section
        self.alerts_card = Card(self, title="Wash Sale Alerts")
        self.alerts_card.pack(fill=tk.X)

        self.alerts_content = self.alerts_card.content

    def refresh(self) -> None:
        """Refresh dashboard data from services or mock data."""
        provider = get_provider()

        # Try to get data from services, fall back to mock
        if provider.is_live and provider.portfolio:
            summary = provider.portfolio.get_portfolio_summary()
        else:
            summary = MockDataFactory.get_portfolio_summary()

        # Update summary cards
        self.cards["total_value"].set_value(f"${summary.total_value:,.2f}")
        self.cards["unrealized"].set_value(
            f"${summary.unrealized_gain_loss:+,.2f}",
            f"{summary.unrealized_gain_loss_pct:+.2f}%",
        )
        self.cards["ytd_harvested"].set_value(f"${summary.ytd_harvested_losses:,.2f}")
        self.cards["pending"].set_value(str(summary.pending_harvest_opportunities))

        # Clear and rebuild opportunities list
        for widget in self.opps_content.winfo_children():
            widget.destroy()

        if provider.is_live and provider.scanner:
            scan_result = provider.scanner.scan()
            opportunities = scan_result.opportunities[:3]
        else:
            opportunities = MockDataFactory.get_harvest_opportunities()[:3]
        self._build_opportunities_table(opportunities)

        # Clear and rebuild alerts list
        for widget in self.alerts_content.winfo_children():
            widget.destroy()

        # Wash sale service is always available
        restrictions = provider.wash_sale.get_active_restrictions()
        if not restrictions:
            restrictions = MockDataFactory.get_active_wash_sale_restrictions()
        self._build_alerts_list(restrictions)

    def _build_opportunities_table(self, opportunities: list) -> None:
        """Build the harvest opportunities table.

        Args:
            opportunities: List of harvest opportunities to display.
        """
        if not opportunities:
            label = tk.Label(
                self.opps_content,
                text="No harvest opportunities available",
                font=Fonts.BODY,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            )
            label.pack(pady=Spacing.MD)
            return

        # Header row - use grid for proper column alignment
        header_frame = tk.Frame(self.opps_content, bg=Colors.BG_SECONDARY)
        header_frame.pack(fill=tk.X, pady=(0, Spacing.SM))

        headers = ["Ticker", "Loss", "Tax Benefit", "Action"]
        weights = [1, 1, 1, 1]

        for i, hdr in enumerate(headers):
            lbl = tk.Label(
                header_frame,
                text=hdr,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            )
            lbl.grid(row=0, column=i, sticky="w", padx=(0, Spacing.MD))
            header_frame.grid_columnconfigure(i, weight=weights[i])

        # Data rows
        for opp in opportunities:
            row_frame = tk.Frame(self.opps_content, bg=Colors.BG_SECONDARY)
            row_frame.pack(fill=tk.X, pady=2)

            # Ticker
            tk.Label(
                row_frame,
                text=opp.ticker,
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            ).grid(row=0, column=0, sticky="w", padx=(0, Spacing.MD))

            # Loss
            tk.Label(
                row_frame,
                text=f"${opp.unrealized_loss:,.2f}",
                font=Fonts.BODY,
                fg=Colors.DANGER_TEXT,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            ).grid(row=0, column=1, sticky="w", padx=(0, Spacing.MD))

            # Tax Benefit
            tk.Label(
                row_frame,
                text=f"${opp.estimated_tax_benefit:,.2f}",
                font=Fonts.BODY,
                fg=Colors.SUCCESS_TEXT,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            ).grid(row=0, column=2, sticky="w", padx=(0, Spacing.MD))

            # Action button
            btn = tk.Button(
                row_frame,
                text="Harvest",
                font=Fonts.CAPTION,
                fg=Colors.BG_PRIMARY,
                bg=Colors.ACCENT,
                activebackground=Colors.ACCENT_HOVER,
                activeforeground=Colors.BG_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                padx=Spacing.SM,
                command=lambda t=opp.ticker: self._on_harvest(t),
            )
            btn.grid(row=0, column=3, sticky="w")

            # Configure row columns to match header
            for i, w in enumerate(weights):
                row_frame.grid_columnconfigure(i, weight=w)

    def _build_alerts_list(self, restrictions: list) -> None:
        """Build the wash sale alerts list.

        Args:
            restrictions: List of active wash sale restrictions.
        """
        if not restrictions:
            label = tk.Label(
                self.alerts_content,
                text="No active wash sale restrictions",
                font=Fonts.BODY,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            )
            label.pack(pady=Spacing.MD)
            return

        for restriction in restrictions[:5]:
            alert_frame = tk.Frame(self.alerts_content, bg=Colors.BG_SECONDARY)
            alert_frame.pack(fill=tk.X, pady=2)

            msg = (
                f"{restriction.ticker}: Restriction expires in "
                f"{restriction.days_remaining} days ({restriction.restriction_end})"
            )

            tk.Label(
                alert_frame,
                text=msg,
                font=Fonts.BODY,
                fg=Colors.WARNING,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            ).pack(fill=tk.X)

    def _on_view_all_opportunities(self) -> None:
        """Handle View All button click - navigate to harvest queue."""
        # Navigation will be handled by parent
        pass

    def _on_harvest(self, ticker: str) -> None:
        """Handle harvest button click.

        Args:
            ticker: The ticker symbol to harvest.
        """
        # Will be implemented to queue harvest action
        pass
