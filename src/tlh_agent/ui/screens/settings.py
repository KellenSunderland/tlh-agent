"""Settings screen for configuring the application."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.theme import Spacing


class SettingsScreen(BaseScreen):
    """Screen for configuring application settings."""

    def _setup_ui(self) -> None:
        """Set up the settings layout."""
        # Header
        header = ttk.Label(self, text="Settings", style="Heading.TLabel")
        header.pack(anchor=tk.W, pady=(0, Spacing.LG))

        # Placeholder content
        placeholder = ttk.Label(
            self,
            text="Configuration options for scanner, rules, and brokerage will be shown here.",
            style="Muted.TLabel",
        )
        placeholder.pack(pady=Spacing.XL)

    def refresh(self) -> None:
        """Refresh settings data."""
        pass
