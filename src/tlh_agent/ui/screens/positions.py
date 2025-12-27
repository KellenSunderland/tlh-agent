"""Positions screen showing all portfolio holdings with lot details."""

import logging
import tkinter as tk
from typing import Any

from tlh_agent.services import get_provider
from tlh_agent.services.portfolio import Position
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.data_table import ColumnDef, DataTable
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing

logger = logging.getLogger(__name__)


class PositionsScreen(BaseScreen):
    """Screen showing all portfolio positions with expandable lot details."""

    def _setup_ui(self) -> None:
        """Set up the positions screen layout."""
        # Header
        header = PageHeader(self, title="Positions", subtitle="Portfolio holdings and lot details")
        header.pack(fill=tk.X, pady=(0, Spacing.LG))
        header.add_action_button("Export CSV", self._on_export)

        # Summary card
        summary_card = Card(self, title="Portfolio Summary")
        summary_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        self.summary_frame = summary_card.content
        self.summary_labels: dict[str, tk.Label] = {}
        for key, label in [
            ("total_value", "Total Value"),
            ("total_cost", "Cost Basis"),
            ("total_gain", "Unrealized G/L"),
            ("positions", "Positions"),
        ]:
            frame = tk.Frame(self.summary_frame, bg=Colors.BG_SECONDARY)
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
                text="$0.00",
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
            )
            value_label.pack(anchor=tk.W)
            self.summary_labels[key] = value_label

        # Positions table in card
        table_card = Card(self, title="Holdings")
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, Spacing.MD))

        columns = [
            ColumnDef("ticker", "Ticker", width=80),
            ColumnDef("name", "Name", width=200),
            ColumnDef("shares", "Shares", width=80, anchor="e"),
            ColumnDef("current_price", "Price", width=100, anchor="e"),
            ColumnDef("market_value", "Value", width=120, anchor="e"),
            ColumnDef("cost_basis", "Cost Basis", width=120, anchor="e"),
            ColumnDef("gain_loss", "Gain/Loss", width=120, anchor="e"),
            ColumnDef("gain_loss_pct", "G/L %", width=80, anchor="e"),
            ColumnDef("status", "Status", width=100),
        ]

        self.table = DataTable(
            table_card.content,
            columns=columns,
            on_select=self._on_position_select,
            on_double_click=self._on_position_double_click,
        )
        self.table.pack(fill=tk.BOTH, expand=True)

        # Lot details panel (below table)
        details_card = Card(self, title="Lot Details")
        details_card.pack(fill=tk.X)

        self.details_frame = details_card.content

        self.details_label = tk.Label(
            self.details_frame,
            text="Select a position to view lot details",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.details_label.pack(fill=tk.X)

    def refresh(self) -> None:
        """Refresh positions data from Alpaca."""
        provider = get_provider()

        if not provider.is_live or not provider.portfolio:
            logger.warning("POSITIONS: Alpaca not connected")
            self._show_not_connected()
            return

        positions = provider.portfolio.get_positions()

        # Update summary
        total_value = sum(p.market_value for p in positions)
        total_cost = sum(p.cost_basis for p in positions)
        total_gain = total_value - total_cost

        self.summary_labels["total_value"].configure(text=f"${total_value:,.2f}")
        self.summary_labels["total_cost"].configure(text=f"${total_cost:,.2f}")

        gain_color = Colors.SUCCESS_TEXT if total_gain >= 0 else Colors.DANGER_TEXT
        self.summary_labels["total_gain"].configure(text=f"${total_gain:+,.2f}", fg=gain_color)
        self.summary_labels["positions"].configure(text=str(len(positions)))

        # Build table data
        table_data = []
        for pos in positions:
            status = ""
            tag = ""
            if pos.wash_sale_until:
                status = "Wash Sale"
                tag = "muted"
            elif pos.unrealized_gain_loss < 0:
                tag = "loss"
            elif pos.unrealized_gain_loss > 0:
                tag = "gain"

            table_data.append(
                {
                    "ticker": pos.ticker,
                    "name": pos.name,
                    "shares": f"{pos.shares:,.2f}",
                    "current_price": f"${pos.current_price:,.2f}",
                    "market_value": f"${pos.market_value:,.2f}",
                    "cost_basis": f"${pos.cost_basis:,.2f}",
                    "gain_loss": f"${pos.unrealized_gain_loss:+,.2f}",
                    "gain_loss_pct": f"{pos.unrealized_gain_loss_pct:+.1f}%",
                    "status": status,
                    "tag": tag,
                    "_position": pos,
                }
            )

        self.table.set_data(table_data)

    def _show_not_connected(self) -> None:
        """Show UI state when Alpaca is not connected."""
        self.summary_labels["total_value"].configure(text="--")
        self.summary_labels["total_cost"].configure(text="--")
        self.summary_labels["total_gain"].configure(text="--")
        self.summary_labels["positions"].configure(text="--")
        self.table.set_data([])

    def _on_position_select(self, row: dict[str, Any]) -> None:
        """Handle position row selection.

        Args:
            row: The selected row data.
        """
        position = row.get("_position")
        if not isinstance(position, Position):
            return

        self._show_lot_details(position)

    def _on_position_double_click(self, row: dict[str, Any]) -> None:
        """Handle position row double-click.

        Args:
            row: The double-clicked row data.
        """
        # Could open a detailed position view
        pass

    def _show_lot_details(self, position: Position) -> None:
        """Show position details.

        Args:
            position: The position to show details for.
        """
        # Clear existing details
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        # Header
        header = tk.Label(
            self.details_frame,
            text=f"Position Details - {position.ticker}",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        header.pack(fill=tk.X, padx=Spacing.MD, pady=(Spacing.SM, Spacing.XS))

        # Position summary (Alpaca doesn't provide lot-level data)
        details = [
            ("Shares", f"{position.shares:,.2f}"),
            ("Avg Cost", f"${position.avg_cost_per_share:,.2f}"),
            ("Cost Basis", f"${position.cost_basis:,.2f}"),
            ("Current Price", f"${position.current_price:,.2f}"),
            ("Market Value", f"${position.market_value:,.2f}"),
            ("Unrealized G/L", f"${position.unrealized_gain_loss:+,.2f}"),
        ]

        for label, value in details:
            row = tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY)
            row.pack(fill=tk.X, padx=Spacing.MD, pady=1)

            tk.Label(
                row,
                text=label,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
                width=15,
                anchor=tk.W,
            ).pack(side=tk.LEFT)

            color = Colors.TEXT_PRIMARY
            if "+" in value and "$" in value:
                color = Colors.SUCCESS_TEXT
            elif "-" in value and "$" in value:
                color = Colors.DANGER_TEXT

            tk.Label(
                row,
                text=value,
                font=Fonts.BODY,
                fg=color,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            ).pack(side=tk.LEFT)

        # Bottom padding
        tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY, height=Spacing.SM).pack()

    def _on_export(self) -> None:
        """Handle export button click."""
        # Will implement CSV export
        pass
