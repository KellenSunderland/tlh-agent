"""Positions screen showing all portfolio holdings with lot details."""

import tkinter as tk
from decimal import Decimal
from typing import Any

from tlh_agent.data.mock_data import MockDataFactory, Position
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.data_table import ColumnDef, DataTable
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class PositionsScreen(BaseScreen):
    """Screen showing all portfolio positions with expandable lot details."""

    def _setup_ui(self) -> None:
        """Set up the positions screen layout."""
        # Header
        header = PageHeader(self, title="Positions", subtitle="Portfolio holdings and lot details")
        header.pack(fill=tk.X, pady=(0, Spacing.LG))
        header.add_action_button("Export CSV", self._on_export)

        # Summary bar
        self.summary_frame = tk.Frame(self, bg=Colors.BG_SECONDARY)
        self.summary_frame.pack(fill=tk.X, pady=(0, Spacing.MD))

        self.summary_labels: dict[str, tk.Label] = {}
        for key, label in [
            ("total_value", "Total Value"),
            ("total_cost", "Cost Basis"),
            ("total_gain", "Unrealized G/L"),
            ("positions", "Positions"),
        ]:
            frame = tk.Frame(self.summary_frame, bg=Colors.BG_SECONDARY)
            frame.pack(side=tk.LEFT, padx=Spacing.LG, pady=Spacing.SM)

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

        # Positions table
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
            self,
            columns=columns,
            on_select=self._on_position_select,
            on_double_click=self._on_position_double_click,
        )
        self.table.pack(fill=tk.BOTH, expand=True, pady=(0, Spacing.MD))

        # Lot details panel (below table)
        self.details_frame = tk.Frame(self, bg=Colors.BG_SECONDARY)
        self.details_frame.pack(fill=tk.X, pady=(0, 0))

        self.details_label = tk.Label(
            self.details_frame,
            text="Select a position to view lot details",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.details_label.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.MD)

    def refresh(self) -> None:
        """Refresh positions data."""
        positions = MockDataFactory.get_positions()

        # Update summary
        total_value = sum(p.market_value for p in positions)
        total_cost = sum(p.total_cost_basis for p in positions)
        total_gain = total_value - total_cost

        self.summary_labels["total_value"].configure(text=f"${total_value:,.2f}")
        self.summary_labels["total_cost"].configure(text=f"${total_cost:,.2f}")

        gain_color = Colors.SUCCESS_TEXT if total_gain >= 0 else Colors.DANGER_TEXT
        self.summary_labels["total_gain"].configure(text=f"${total_gain:+,.2f}", fg=gain_color)
        self.summary_labels["positions"].configure(text=str(len(positions)))

        # Build table data
        table_data = []
        for pos in positions:
            gain_loss = pos.unrealized_gain_loss
            gain_loss_pct = (
                (gain_loss / pos.total_cost_basis * 100) if pos.total_cost_basis else Decimal(0)
            )

            status = ""
            tag = ""
            if pos.wash_sale_until:
                status = "Wash Sale"
                tag = "muted"
            elif gain_loss < 0:
                tag = "loss"
            elif gain_loss > 0:
                tag = "gain"

            table_data.append(
                {
                    "ticker": pos.ticker,
                    "name": pos.name,
                    "shares": f"{pos.total_shares:,.2f}",
                    "current_price": f"${pos.current_price:,.2f}",
                    "market_value": f"${pos.market_value:,.2f}",
                    "cost_basis": f"${pos.total_cost_basis:,.2f}",
                    "gain_loss": f"${gain_loss:+,.2f}",
                    "gain_loss_pct": f"{gain_loss_pct:+.1f}%",
                    "status": status,
                    "tag": tag,
                    "_position": pos,  # Store original position for details
                }
            )

        self.table.set_data(table_data)

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
        """Show lot details for a position.

        Args:
            position: The position to show lot details for.
        """
        # Clear existing details
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        # Header
        header = tk.Label(
            self.details_frame,
            text=f"Lot Details - {position.ticker}",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        header.pack(fill=tk.X, padx=Spacing.MD, pady=(Spacing.SM, Spacing.XS))

        # Lot table header
        lot_header = tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY)
        lot_header.pack(fill=tk.X, padx=Spacing.MD)

        headers = ["Shares", "Cost/Share", "Total Cost", "Acquired", "Holding Period", "G/L"]
        widths = [80, 100, 100, 100, 100, 100]

        for h, w in zip(headers, widths, strict=False):
            tk.Label(
                lot_header,
                text=h,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
                width=w // 8,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=2)

        # Lot rows
        for lot in position.lots:
            lot_row = tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY)
            lot_row.pack(fill=tk.X, padx=Spacing.MD)

            gain_loss = (position.current_price - lot.cost_per_share) * lot.shares
            holding_days = (
                (lot.acquired_date.today() - lot.acquired_date).days
                if hasattr(lot.acquired_date, "today")
                else 0
            )

            # Recalculate holding period properly
            from datetime import date

            holding_days = (date.today() - lot.acquired_date).days
            holding_text = f"{holding_days}d"
            if holding_days > 365:
                holding_text += " (LT)"
            else:
                holding_text += " (ST)"

            values = [
                f"{lot.shares:,.2f}",
                f"${lot.cost_per_share:,.2f}",
                f"${lot.total_cost_basis:,.2f}",
                lot.acquired_date.strftime("%Y-%m-%d"),
                holding_text,
                f"${gain_loss:+,.2f}",
            ]

            for val, w in zip(values, widths, strict=False):
                color = Colors.TEXT_PRIMARY
                if "+" in val and "$" in val:
                    color = Colors.SUCCESS_TEXT
                elif "-" in val and "$" in val:
                    color = Colors.DANGER_TEXT

                tk.Label(
                    lot_row,
                    text=val,
                    font=Fonts.BODY,
                    fg=color,
                    bg=Colors.BG_SECONDARY,
                    width=w // 8,
                    anchor=tk.W,
                ).pack(side=tk.LEFT, padx=2)

        # Bottom padding
        tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY, height=Spacing.SM).pack()

    def _on_export(self) -> None:
        """Handle export button click."""
        # Will implement CSV export
        pass
