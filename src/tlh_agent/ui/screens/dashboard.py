"""Dashboard screen with portfolio summary and key metrics."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.data.mock_data import MockDataFactory
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.summary_card import SummaryCard
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class DashboardScreen(BaseScreen):
    """Main dashboard showing portfolio overview and harvest opportunities."""

    def _setup_ui(self) -> None:
        """Set up the dashboard layout."""
        # Header
        header = ttk.Label(self, text="Dashboard", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Summary cards row
        cards_frame = ttk.Frame(self, style="TFrame")
        cards_frame.pack(fill=tk.X, pady=(0, Spacing.LG))

        self.cards: dict[str, SummaryCard] = {}

        card_configs = [
            ("total_value", "Total Value", "$0.00", None),
            ("unrealized", "Unrealized G/L", "$0.00", None),
            ("ytd_harvested", "YTD Harvested", "$0.00", None),
            ("pending", "Pending Harvests", "0", None),
        ]

        for card_id, label, value, trend in card_configs:
            card = SummaryCard(cards_frame, label=label, value=value, trend=trend)
            card.pack(side=tk.LEFT, padx=(0, Spacing.MD))
            self.cards[card_id] = card

        # Top Harvest Opportunities section
        opps_header_frame = ttk.Frame(self, style="TFrame")
        opps_header_frame.pack(fill=tk.X, pady=(Spacing.MD, Spacing.SM))

        opps_label = ttk.Label(
            opps_header_frame, text="Top Harvest Opportunities", style="Subheading.TLabel"
        )
        opps_label.pack(side=tk.LEFT)

        view_all_btn = ttk.Button(
            opps_header_frame,
            text="View All",
            style="TButton",
            command=self._on_view_all_opportunities,
        )
        view_all_btn.pack(side=tk.RIGHT)

        # Opportunities table
        self.opps_frame = ttk.Frame(self, style="Card.TFrame")
        self.opps_frame.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Wash Sale Alerts section
        alerts_label = ttk.Label(self, text="Wash Sale Alerts", style="Subheading.TLabel")
        alerts_label.pack(anchor=tk.W, pady=(Spacing.MD, Spacing.SM))

        self.alerts_frame = ttk.Frame(self, style="Card.TFrame")
        self.alerts_frame.pack(fill=tk.X)

    def refresh(self) -> None:
        """Refresh dashboard data from mock data source."""
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
        for widget in self.opps_frame.winfo_children():
            widget.destroy()

        opportunities = MockDataFactory.get_harvest_opportunities()[:3]
        self._build_opportunities_table(opportunities)

        # Clear and rebuild alerts list
        for widget in self.alerts_frame.winfo_children():
            widget.destroy()

        restrictions = MockDataFactory.get_active_wash_sale_restrictions()
        self._build_alerts_list(restrictions)

    def _build_opportunities_table(self, opportunities: list) -> None:
        """Build the harvest opportunities table.

        Args:
            opportunities: List of harvest opportunities to display.
        """
        if not opportunities:
            label = ttk.Label(
                self.opps_frame,
                text="No harvest opportunities available",
                style="Muted.TLabel",
            )
            label.configure(background=Colors.BG_SECONDARY)
            label.pack(padx=Spacing.MD, pady=Spacing.MD)
            return

        # Header row
        header_frame = tk.Frame(self.opps_frame, bg=Colors.BG_SECONDARY)
        header_frame.pack(fill=tk.X, padx=Spacing.SM, pady=(Spacing.SM, 0))

        headers = ["Ticker", "Loss", "Tax Benefit", "Action"]
        widths = [100, 120, 120, 100]

        for header, width in zip(headers, widths, strict=False):
            lbl = tk.Label(
                header_frame,
                text=header,
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
                width=width // 10,
                anchor=tk.W,
            )
            lbl.pack(side=tk.LEFT, padx=Spacing.SM)

        # Data rows
        for opp in opportunities:
            row_frame = tk.Frame(self.opps_frame, bg=Colors.BG_SECONDARY)
            row_frame.pack(fill=tk.X, padx=Spacing.SM, pady=2)

            # Ticker
            tk.Label(
                row_frame,
                text=opp.ticker,
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
                width=10,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=Spacing.SM)

            # Loss
            tk.Label(
                row_frame,
                text=f"${opp.unrealized_loss:,.2f}",
                font=Fonts.BODY,
                fg=Colors.DANGER_TEXT,
                bg=Colors.BG_SECONDARY,
                width=12,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=Spacing.SM)

            # Tax Benefit
            tk.Label(
                row_frame,
                text=f"${opp.estimated_tax_benefit:,.2f}",
                font=Fonts.BODY,
                fg=Colors.SUCCESS_TEXT,
                bg=Colors.BG_SECONDARY,
                width=12,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=Spacing.SM)

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
                command=lambda t=opp.ticker: self._on_harvest(t),
            )
            btn.pack(side=tk.LEFT, padx=Spacing.SM)

        # Bottom padding
        ttk.Frame(self.opps_frame, style="Card.TFrame", height=Spacing.SM).pack()

    def _build_alerts_list(self, restrictions: list) -> None:
        """Build the wash sale alerts list.

        Args:
            restrictions: List of active wash sale restrictions.
        """
        if not restrictions:
            label = ttk.Label(
                self.alerts_frame,
                text="No active wash sale restrictions",
                style="Muted.TLabel",
            )
            label.configure(background=Colors.BG_SECONDARY)
            label.pack(padx=Spacing.MD, pady=Spacing.MD)
            return

        for restriction in restrictions[:5]:
            alert_frame = tk.Frame(self.alerts_frame, bg=Colors.BG_SECONDARY)
            alert_frame.pack(fill=tk.X, padx=Spacing.SM, pady=2)

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
            ).pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Bottom padding
        ttk.Frame(self.alerts_frame, style="Card.TFrame", height=Spacing.SM).pack()

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
