"""Trade queue screen for managing pending trade recommendations.

Displays trades from multiple sources:
- Harvest opportunities (tax-loss harvesting sells)
- Index buys (S&P 500 tracking purchases)
- Rebalance trades (drift correction)
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

from tlh_agent.data.mock_data import HarvestOpportunity, MockDataFactory
from tlh_agent.services import get_provider
from tlh_agent.services.scanner import HarvestOpportunity as LiveHarvestOpportunity
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.data_table import ColumnDef, DataTable
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class HarvestQueueScreen(BaseScreen):
    """Screen for reviewing and acting on pending trades from all sources."""

    def _setup_ui(self) -> None:
        """Set up the trade queue layout."""
        # Header
        header = PageHeader(self, title="Trade Queue", subtitle="Review and execute pending trades")
        header.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Total savings display in header actions
        self.total_savings_label = tk.Label(
            header.actions,
            text="Potential Savings: $0.00",
            font=Fonts.BODY_BOLD,
            fg=Colors.SUCCESS_TEXT,
            bg=Colors.BG_PRIMARY,
        )
        self.total_savings_label.pack(side=tk.RIGHT)

        # Summary card
        summary_card = Card(self, title="Queue Summary")
        summary_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        summary_content = summary_card.content
        self.summary_labels: dict[str, tk.Label] = {}
        for key, label in [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("total_loss", "Total Loss"),
            ("tax_benefit", "Tax Benefit"),
        ]:
            frame = tk.Frame(summary_content, bg=Colors.BG_SECONDARY)
            frame.pack(side=tk.LEFT, padx=(0, Spacing.XL))

            tk.Label(
                frame,
                text=label,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(anchor=tk.W)

            value_label = tk.Label(
                frame,
                text="0",
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
            )
            value_label.pack(anchor=tk.W)
            self.summary_labels[key] = value_label

        # Trade queue table in card
        table_card = Card(self, title="Pending Trades")
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, Spacing.MD))

        columns = [
            ColumnDef("trade_type", "Type", width=80),
            ColumnDef("status", "Status", width=70),
            ColumnDef("ticker", "Ticker", width=70),
            ColumnDef("name", "Name", width=150),
            ColumnDef("action", "Action", width=60),
            ColumnDef("shares", "Shares", width=70, anchor="e"),
            ColumnDef("amount", "Amount", width=90, anchor="e"),
            ColumnDef("tax_benefit", "Tax Benefit", width=90, anchor="e"),
        ]

        self.table = DataTable(
            table_card.content,
            columns=columns,
            on_select=self._on_select,
        )
        self.table.pack(fill=tk.BOTH, expand=True)

        # Action buttons row
        action_frame = ttk.Frame(self, style="TFrame")
        action_frame.pack(fill=tk.X, pady=(0, Spacing.MD))

        # Selected item actions
        self.approve_btn = tk.Button(
            action_frame,
            text="Approve Selected",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.SUCCESS,
            activebackground="#28a745",
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_approve,
        )
        self.approve_btn.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self.reject_btn = tk.Button(
            action_frame,
            text="Reject Selected",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.DANGER,
            activebackground="#c82333",
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_reject,
        )
        self.reject_btn.pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Bulk actions
        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=Spacing.MD
        )

        tk.Button(
            action_frame,
            text="Approve All",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BORDER,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_approve_all,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        tk.Button(
            action_frame,
            text="Reject All",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BORDER,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_reject_all,
        ).pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Execute button (right aligned)
        tk.Button(
            action_frame,
            text="Execute Approved",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.ACCENT,
            activebackground=Colors.ACCENT_HOVER,
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.LG,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_execute,
        ).pack(side=tk.RIGHT)

        # Details panel in card
        details_card = Card(self, title="Details")
        details_card.pack(fill=tk.X)

        self.details_frame = details_card.content

        self.details_label = tk.Label(
            self.details_frame,
            text="Select a trade to view details",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.details_label.pack(fill=tk.X)

    def refresh(self) -> None:
        """Refresh harvest queue data."""
        provider = get_provider()

        if provider.is_live and provider.scanner:
            scan_result = provider.scanner.scan()
            opportunities = scan_result.opportunities
        else:
            opportunities = MockDataFactory.get_harvest_opportunities()

        # Update summary
        pending_count = sum(1 for o in opportunities if o.status == "pending")
        approved_count = sum(1 for o in opportunities if o.status == "approved")
        active_statuses = ("pending", "approved")
        total_loss = sum(o.unrealized_loss for o in opportunities if o.status in active_statuses)
        total_benefit = sum(
            o.estimated_tax_benefit for o in opportunities if o.status in active_statuses
        )

        self.summary_labels["pending"].configure(text=str(pending_count))
        self.summary_labels["approved"].configure(text=str(approved_count))
        self.summary_labels["total_loss"].configure(
            text=f"${total_loss:,.2f}",
            fg=Colors.DANGER_TEXT,
        )
        self.summary_labels["tax_benefit"].configure(
            text=f"${total_benefit:,.2f}",
            fg=Colors.SUCCESS_TEXT,
        )

        # Update total savings
        self.total_savings_label.configure(text=f"Potential Savings: ${total_benefit:,.2f}")

        # Build table data
        table_data = []
        for opp in opportunities:
            status_display = opp.status.title()
            tag = ""
            if opp.status == "approved":
                tag = "gain"
            elif opp.status in ("rejected", "expired"):
                tag = "muted"

            # Calculate amount (market value)
            amount = opp.shares * opp.current_price

            table_data.append(
                {
                    "trade_type": "Harvest",
                    "status": status_display,
                    "ticker": opp.ticker,
                    "name": opp.name,
                    "action": "Sell",
                    "shares": f"{opp.shares:,.2f}",
                    "amount": f"${amount:,.2f}",
                    "tax_benefit": f"${opp.estimated_tax_benefit:,.2f}",
                    "tag": tag,
                    "_opportunity": opp,
                }
            )

        self.table.set_data(table_data)

    def _on_select(self, row: dict[str, Any]) -> None:
        """Handle row selection."""
        opp = row.get("_opportunity")
        if not isinstance(opp, (HarvestOpportunity, LiveHarvestOpportunity)):
            return

        self._show_details(opp)

    def _show_details(self, opp: HarvestOpportunity) -> None:
        """Show details for a harvest opportunity."""
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        # Details grid
        details = tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY)
        details.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        # Row 1: Ticker info
        row1 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row1.pack(fill=tk.X, pady=2)

        tk.Label(
            row1,
            text=f"{opp.ticker} - {opp.name}",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT)

        tk.Label(
            row1,
            text=f"Status: {opp.status.title()}",
            font=Fonts.BODY,
            fg=Colors.ACCENT if opp.status == "approved" else Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.RIGHT)

        # Row 2: Financial details
        row2 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row2.pack(fill=tk.X, pady=2)

        for label, value, color in [
            ("Shares:", f"{opp.shares:,.2f}", Colors.TEXT_PRIMARY),
            ("Current Price:", f"${opp.current_price:,.2f}", Colors.TEXT_PRIMARY),
            ("Cost Basis:", f"${opp.cost_basis:,.2f}", Colors.TEXT_PRIMARY),
            ("Unrealized Loss:", f"${opp.unrealized_loss:,.2f}", Colors.DANGER_TEXT),
            ("Est. Tax Benefit:", f"${opp.estimated_tax_benefit:,.2f}", Colors.SUCCESS_TEXT),
        ]:
            tk.Label(
                row2,
                text=f"{label} {value}",
                font=Fonts.BODY,
                fg=color,
                bg=Colors.BG_SECONDARY,
            ).pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Row 3: Action recommendation
        row3 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row3.pack(fill=tk.X, pady=2)

        action_text = f"Recommended: {opp.recommended_action.title()}"
        if opp.swap_target:
            action_text += f" to {opp.swap_target}"

        tk.Label(
            row3,
            text=action_text,
            font=Fonts.BODY,
            fg=Colors.ACCENT,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT)

    def _on_approve(self) -> None:
        """Approve selected opportunity."""
        selected = self.table.get_selected()
        if selected:
            opp = selected.get("_opportunity")
            if opp and hasattr(opp, "id"):
                provider = get_provider()
                if provider.scanner:
                    provider.scanner.approve_harvest(opp.id)
                    self.refresh()

    def _on_reject(self) -> None:
        """Reject selected opportunity."""
        selected = self.table.get_selected()
        if selected:
            opp = selected.get("_opportunity")
            if opp and hasattr(opp, "id"):
                provider = get_provider()
                if provider.scanner:
                    provider.scanner.reject_harvest(opp.id)
                    self.refresh()

    def _on_approve_all(self) -> None:
        """Approve all pending opportunities."""
        provider = get_provider()
        if provider.scanner:
            scan_result = provider.scanner.scan()
            for opp in scan_result.opportunities:
                if opp.status == "pending":
                    provider.scanner.approve_harvest(opp.id)
            self.refresh()

    def _on_reject_all(self) -> None:
        """Reject all pending opportunities."""
        provider = get_provider()
        if provider.scanner:
            scan_result = provider.scanner.scan()
            for opp in scan_result.opportunities:
                if opp.status == "pending":
                    provider.scanner.reject_harvest(opp.id)
            self.refresh()

    def _on_execute(self) -> None:
        """Execute all approved harvests."""
        provider = get_provider()
        if provider.execution and provider.scanner:
            scan_result = provider.scanner.scan()
            for opp in scan_result.opportunities:
                if opp.status == "approved":
                    provider.execution.execute_harvest(opp)
            self.refresh()
