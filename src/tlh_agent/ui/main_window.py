"""Main window with sidebar navigation and content area."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.components.nav_sidebar import NavSidebar
from tlh_agent.ui.theme import Theme


class MainWindow(ttk.Frame):
    """Main application window with navigation sidebar and content area."""

    def __init__(self, parent: tk.Tk) -> None:
        """Initialize the main window.

        Args:
            parent: The root tkinter window.
        """
        super().__init__(parent, style="TFrame")

        self._screens: dict[str, ttk.Frame] = {}
        self._current_screen: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the main window layout."""
        # Sidebar
        self.sidebar = NavSidebar(self, on_navigate=self._on_navigate)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # Separator between sidebar and content
        separator = ttk.Separator(self, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, fill=tk.Y)

        # Content area
        self.content_frame = ttk.Frame(self, style="TFrame")
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Initialize screens (lazy loading)
        self._init_screens()

        # Show dashboard by default
        self._show_screen("dashboard")

    def _init_screens(self) -> None:
        """Initialize all application screens."""
        from tlh_agent.ui.screens.dashboard import DashboardScreen
        from tlh_agent.ui.screens.harvest_queue import HarvestQueueScreen
        from tlh_agent.ui.screens.loss_ledger import LossLedgerScreen
        from tlh_agent.ui.screens.positions import PositionsScreen
        from tlh_agent.ui.screens.settings import SettingsScreen
        from tlh_agent.ui.screens.trade_history import TradeHistoryScreen
        from tlh_agent.ui.screens.wash_calendar import WashCalendarScreen

        screen_classes = {
            "dashboard": DashboardScreen,
            "positions": PositionsScreen,
            "harvest": HarvestQueueScreen,
            "wash_sales": WashCalendarScreen,
            "history": TradeHistoryScreen,
            "ledger": LossLedgerScreen,
            "settings": SettingsScreen,
        }

        for name, screen_class in screen_classes.items():
            screen = screen_class(self.content_frame)
            self._screens[name] = screen

    def _on_navigate(self, screen_name: str) -> None:
        """Handle navigation to a different screen.

        Args:
            screen_name: The name of the screen to navigate to.
        """
        self._show_screen(screen_name)

    def _show_screen(self, screen_name: str) -> None:
        """Show the specified screen and hide others.

        Args:
            screen_name: The name of the screen to show.
        """
        if screen_name == self._current_screen:
            return

        # Hide current screen
        if self._current_screen and self._current_screen in self._screens:
            self._screens[self._current_screen].pack_forget()

        # Show new screen
        if screen_name in self._screens:
            self._screens[screen_name].pack(
                fill=tk.BOTH,
                expand=True,
                padx=Theme.spacing.LG,
                pady=Theme.spacing.LG,
            )
            self._current_screen = screen_name
            self.sidebar.set_active(screen_name)
