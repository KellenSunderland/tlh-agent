"""Loss ledger screen tracking cumulative harvested losses."""

import tkinter as tk
from decimal import Decimal

from tlh_agent.data.mock_data import MockDataFactory
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class LossLedgerScreen(BaseScreen):
    """Screen tracking harvested losses and carryforward balances."""

    def _setup_ui(self) -> None:
        """Set up the loss ledger layout."""
        # Header
        header = PageHeader(
            self, title="Loss Ledger", subtitle="Carryforward losses and tax benefits"
        )
        header.pack(fill=tk.X, pady=(0, Spacing.LG))
        header.add_action_button("Export Tax Report", self._on_export)

        # Carryforward summary card
        summary_card = Card(self, title="Available Carryforward")
        summary_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        summary_content = summary_card.content

        # Total carryforward
        self.total_carryforward_label = tk.Label(
            summary_content,
            text="$0.00",
            font=("Inter", 32, "bold"),
            fg=Colors.ACCENT,
            bg=Colors.BG_SECONDARY,
        )
        self.total_carryforward_label.pack(anchor=tk.W, pady=(0, Spacing.XS))

        # Breakdown
        breakdown_frame = tk.Frame(summary_content, bg=Colors.BG_SECONDARY)
        breakdown_frame.pack(anchor=tk.W)

        self.st_carryforward_label = tk.Label(
            breakdown_frame,
            text="Short-term: $0.00",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
        )
        self.st_carryforward_label.pack(side=tk.LEFT, padx=(0, Spacing.LG))

        self.lt_carryforward_label = tk.Label(
            breakdown_frame,
            text="Long-term: $0.00",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
        )
        self.lt_carryforward_label.pack(side=tk.LEFT)

        # Year-by-year breakdown card
        year_card = Card(self, title="Year-by-Year Breakdown")
        year_card.pack(fill=tk.BOTH, expand=True)

        self.year_table_frame = year_card.content

    def refresh(self) -> None:
        """Refresh loss ledger data."""
        ledger_entries = MockDataFactory.get_loss_ledger()

        # Calculate carryforward totals
        # The most recent year's carryforward is the available amount
        if ledger_entries:
            latest = ledger_entries[0]  # Assuming sorted by year descending
            total_cf = latest.carryforward

            # Calculate ST/LT breakdown (simplified - would need more detailed tracking)
            st_cf = total_cf * Decimal("0.6")  # Approximate split
            lt_cf = total_cf * Decimal("0.4")

            self.total_carryforward_label.configure(text=f"${total_cf:,.2f}")
            self.st_carryforward_label.configure(text=f"Short-term: ${st_cf:,.2f}")
            self.lt_carryforward_label.configure(text=f"Long-term: ${lt_cf:,.2f}")

        # Build year table
        self._build_year_table(ledger_entries)

    def _build_year_table(self, entries: list) -> None:
        """Build the year-by-year breakdown table.

        Args:
            entries: List of loss ledger entries.
        """
        # Clear existing content
        for widget in self.year_table_frame.winfo_children():
            widget.destroy()

        if not entries:
            tk.Label(
                self.year_table_frame,
                text="No loss history available",
                font=Fonts.BODY,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(padx=Spacing.MD, pady=Spacing.MD)
            return

        # Table header
        header_frame = tk.Frame(self.year_table_frame, bg=Colors.BG_TERTIARY)
        header_frame.pack(fill=tk.X)

        headers = ["Year", "Short-Term", "Long-Term", "Total Losses", "Used", "Carryforward"]
        widths = [80, 120, 120, 120, 120, 120]

        for header, width in zip(headers, widths, strict=False):
            tk.Label(
                header_frame,
                text=header,
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_TERTIARY,
                width=width // 8,
                anchor=tk.W,
                padx=Spacing.SM,
                pady=Spacing.SM,
            ).pack(side=tk.LEFT)

        # Data rows
        for i, entry in enumerate(entries):
            bg_color = Colors.BG_SECONDARY if i % 2 == 0 else Colors.BG_TERTIARY
            row_frame = tk.Frame(self.year_table_frame, bg=bg_color)
            row_frame.pack(fill=tk.X)

            total_losses = entry.short_term_losses + entry.long_term_losses

            values = [
                str(entry.year),
                f"${entry.short_term_losses:,.2f}",
                f"${entry.long_term_losses:,.2f}",
                f"${total_losses:,.2f}",
                f"${entry.used_against_gains:,.2f}",
                f"${entry.carryforward:,.2f}",
            ]

            colors = [
                Colors.TEXT_PRIMARY,
                Colors.DANGER_TEXT,
                Colors.DANGER_TEXT,
                Colors.DANGER_TEXT,
                Colors.SUCCESS_TEXT,
                Colors.ACCENT,
            ]

            for value, width, color in zip(values, widths, colors, strict=False):
                tk.Label(
                    row_frame,
                    text=value,
                    font=Fonts.BODY,
                    fg=color,
                    bg=bg_color,
                    width=width // 8,
                    anchor=tk.W,
                    padx=Spacing.SM,
                    pady=Spacing.SM,
                ).pack(side=tk.LEFT)

        # Explanation text
        explanation_frame = tk.Frame(self.year_table_frame, bg=Colors.BG_PRIMARY)
        explanation_frame.pack(fill=tk.X, pady=Spacing.MD)

        explanation_text = (
            "Note: Harvested losses can offset capital gains. Up to $3,000 of excess "
            "losses can be deducted against ordinary income per year. Unused losses "
            "carry forward indefinitely."
        )
        tk.Label(
            explanation_frame,
            text=explanation_text,
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY,
            wraplength=700,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _on_export(self) -> None:
        """Export tax report."""
        # Would implement tax report export
        pass
