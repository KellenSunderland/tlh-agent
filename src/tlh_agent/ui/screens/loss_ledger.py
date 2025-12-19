"""Loss ledger screen tracking cumulative harvested losses."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class LossLedgerScreen(BaseScreen):
    """Screen tracking harvested losses and carryforward balances."""

    def _setup_ui(self) -> None:
        """Set up the loss ledger layout."""
        # Header
        header = ttk.Label(self, text="Loss Ledger", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Carryforward summary and year-by-year breakdown will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh loss ledger data."""
        pass
