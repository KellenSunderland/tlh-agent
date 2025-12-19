"""Positions screen showing all portfolio holdings with lot details."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class PositionsScreen(BaseScreen):
    """Screen showing all portfolio positions with expandable lot details."""

    def _setup_ui(self) -> None:
        """Set up the positions screen layout."""
        # Header
        header = ttk.Label(self, text="Positions", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Positions table with expandable lot details will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh positions data."""
        pass
