"""Trade history screen showing executed trades."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class TradeHistoryScreen(BaseScreen):
    """Screen showing log of all executed trades with filtering."""

    def _setup_ui(self) -> None:
        """Set up the trade history layout."""
        # Header
        header = ttk.Label(self, text="Trade History", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Filterable trade history table with export options will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh trade history data."""
        pass
