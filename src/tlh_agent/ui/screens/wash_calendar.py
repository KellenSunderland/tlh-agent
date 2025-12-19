"""Wash sale calendar screen showing restriction windows."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class WashCalendarScreen(BaseScreen):
    """Screen showing visual calendar of wash sale restriction windows."""

    def _setup_ui(self) -> None:
        """Set up the wash calendar layout."""
        # Header
        header = ttk.Label(self, text="Wash Sale Calendar", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Visual calendar with 61-day wash sale windows will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh wash sale calendar data."""
        pass
