"""Trade history screen showing executed trades."""

import tkinter as tk
from tkinter import ttk
from typing import Any

from tlh_agent.data.mock_data import MockDataFactory, Trade
from tlh_agent.services import get_provider
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.data_table import ColumnDef, DataTable
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class TradeHistoryScreen(BaseScreen):
    """Screen showing log of all executed trades with filtering."""

    def _setup_ui(self) -> None:
        """Set up the trade history layout."""
        # Header
        header = PageHeader(
            self, title="Trade History", subtitle="Executed trades and harvest events"
        )
        header.pack(fill=tk.X, pady=(0, Spacing.LG))
        header.add_action_button("Export CSV", self._on_export)

        # Filters card
        filters_card = Card(self, title="Filters")
        filters_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        filter_content = filters_card.content

        # Filter row
        filter_row = tk.Frame(filter_content, bg=Colors.BG_SECONDARY)
        filter_row.pack(fill=tk.X, pady=(0, Spacing.SM))

        # Date range filter
        tk.Label(
            filter_row,
            text="Date Range:",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self.date_range_var = tk.StringVar(value="All Time")
        date_options = [
            "All Time",
            "Last 7 Days",
            "Last 30 Days",
            "Last 90 Days",
            "YTD",
            "Last Year",
        ]
        date_dropdown = ttk.Combobox(
            filter_row,
            textvariable=self.date_range_var,
            values=date_options,
            state="readonly",
            width=15,
        )
        date_dropdown.pack(side=tk.LEFT, padx=(0, Spacing.LG))
        date_dropdown.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())

        # Type filter
        tk.Label(
            filter_row,
            text="Type:",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self.type_var = tk.StringVar(value="All")
        type_options = ["All", "Buy", "Sell", "Harvests Only"]
        type_dropdown = ttk.Combobox(
            filter_row,
            textvariable=self.type_var,
            values=type_options,
            state="readonly",
            width=12,
        )
        type_dropdown.pack(side=tk.LEFT, padx=(0, Spacing.LG))
        type_dropdown.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())

        # Ticker search
        tk.Label(
            filter_row,
            text="Ticker:",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self.ticker_var = tk.StringVar()
        ticker_entry = ttk.Entry(
            filter_row,
            textvariable=self.ticker_var,
            width=10,
        )
        ticker_entry.pack(side=tk.LEFT, padx=(0, Spacing.SM))
        ticker_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        # Clear filters button
        tk.Button(
            filter_row,
            text="Clear",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            relief=tk.FLAT,
            padx=Spacing.SM,
            pady=2,
            cursor="hand2",
            command=self._clear_filters,
        ).pack(side=tk.LEFT)

        # Summary stats row
        stats_row = tk.Frame(filter_content, bg=Colors.BG_SECONDARY)
        stats_row.pack(fill=tk.X)

        self.stats_labels: dict[str, tk.Label] = {}
        for key, label in [
            ("total_trades", "Total Trades"),
            ("total_sold", "Total Sold"),
            ("total_bought", "Total Bought"),
        ]:
            stat_frame = tk.Frame(stats_row, bg=Colors.BG_SECONDARY)
            stat_frame.pack(side=tk.LEFT, padx=(0, Spacing.XL))

            tk.Label(
                stat_frame,
                text=f"{label}:",
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(side=tk.LEFT)

            value_label = tk.Label(
                stat_frame,
                text="0",
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
            )
            value_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))
            self.stats_labels[key] = value_label

        # Trade history table in a card
        table_card = Card(self, title="Trade Log")
        table_card.pack(fill=tk.BOTH, expand=True)

        columns = [
            ColumnDef("date", "Date", width=100),
            ColumnDef("type", "Type", width=60),
            ColumnDef("ticker", "Ticker", width=80),
            ColumnDef("shares", "Shares", width=80, anchor="e"),
            ColumnDef("price", "Price", width=100, anchor="e"),
            ColumnDef("total", "Total", width=120, anchor="e"),
            ColumnDef("harvest_id", "Harvest ID", width=100),
        ]

        self.table = DataTable(
            table_card.content,
            columns=columns,
            on_select=self._on_select,
        )
        self.table.pack(fill=tk.BOTH, expand=True)

        # Store all trades for filtering
        self._all_trades: list[dict[str, Any]] = []

    def refresh(self) -> None:
        """Refresh trade history data."""
        provider = get_provider()

        if provider.is_live and provider.portfolio:
            trades = provider.portfolio.get_trade_history()
        else:
            trades = MockDataFactory.get_trade_history()

        # Build table data
        self._all_trades = []
        for trade in trades:
            tag = "gain" if trade.trade_type == "buy" else "loss"

            self._all_trades.append(
                {
                    "date": trade.executed_at.strftime("%Y-%m-%d"),
                    "type": trade.trade_type.upper(),
                    "ticker": trade.ticker,
                    "shares": f"{trade.shares:,.2f}",
                    "price": f"${trade.price_per_share:,.2f}",
                    "total": f"${trade.total_value:,.2f}",
                    "harvest_id": trade.harvest_event_id or "-",
                    "tag": tag,
                    "_trade": trade,
                }
            )

        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filters to the data."""
        filtered = self._all_trades.copy()

        # Type filter
        type_filter = self.type_var.get()
        if type_filter == "Buy":
            filtered = [t for t in filtered if t["type"] == "BUY"]
        elif type_filter == "Sell":
            filtered = [t for t in filtered if t["type"] == "SELL"]
        elif type_filter == "Harvests Only":
            filtered = [t for t in filtered if t["harvest_id"] != "-"]

        # Ticker filter
        ticker_filter = self.ticker_var.get().upper().strip()
        if ticker_filter:
            filtered = [t for t in filtered if ticker_filter in t["ticker"]]

        # Update table
        self.table.set_data(filtered)

        # Update stats
        total_trades = len(filtered)
        total_sold = sum(
            t["_trade"].total_value for t in filtered if t["_trade"].trade_type == "sell"
        )
        total_bought = sum(
            t["_trade"].total_value for t in filtered if t["_trade"].trade_type == "buy"
        )

        self.stats_labels["total_trades"].configure(text=str(total_trades))
        self.stats_labels["total_sold"].configure(
            text=f"${total_sold:,.2f}",
            fg=Colors.DANGER_TEXT,
        )
        self.stats_labels["total_bought"].configure(
            text=f"${total_bought:,.2f}",
            fg=Colors.SUCCESS_TEXT,
        )

    def _clear_filters(self) -> None:
        """Reset all filters."""
        self.date_range_var.set("All Time")
        self.type_var.set("All")
        self.ticker_var.set("")
        self._apply_filters()

    def _on_select(self, row: dict[str, Any]) -> None:
        """Handle row selection."""
        trade = row.get("_trade")
        if isinstance(trade, Trade):
            # Could show trade details
            pass

    def _on_export(self) -> None:
        """Export trade history to CSV."""
        # Would implement CSV export
        pass
