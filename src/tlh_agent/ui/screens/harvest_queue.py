"""Harvest queue screen for managing pending harvest recommendations."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class HarvestQueueScreen(BaseScreen):
    """Screen for reviewing and acting on harvest recommendations."""

    def _setup_ui(self) -> None:
        """Set up the harvest queue layout."""
        # Header
        header = ttk.Label(self, text="Harvest Queue", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Pending harvest recommendations with approve/reject actions will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh harvest queue data."""
        pass
