"""Main window with sidebar navigation and content area."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.services import get_provider
from tlh_agent.ui.components.assistant_pane import AssistantPane
from tlh_agent.ui.components.nav_sidebar import NavSidebar
from tlh_agent.ui.theme import Colors, Fonts, Theme


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
        self._assistant_visible: bool = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the main window layout."""
        # Sidebar
        self.sidebar = NavSidebar(self, on_navigate=self._on_navigate)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # Separator between sidebar and content
        separator = ttk.Separator(self, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, fill=tk.Y)

        # Content wrapper (for banner + screens)
        content_wrapper = ttk.Frame(self, style="TFrame")
        content_wrapper.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mock data banner (shown when not connected to live data)
        self._mock_banner: tk.Frame | None = None
        provider = get_provider()
        if not provider.is_live:
            self._mock_banner = tk.Frame(content_wrapper, bg=Colors.WARNING, height=40)
            self._mock_banner.pack(fill=tk.X)
            self._mock_banner.pack_propagate(False)

            banner_content = tk.Frame(self._mock_banner, bg=Colors.WARNING)
            banner_content.pack(fill=tk.X, expand=True)

            tk.Label(
                banner_content,
                text="DEMO MODE - Displaying sample data. Connect Alpaca API for live data.",
                font=Fonts.BODY_BOLD,
                fg=Colors.BG_PRIMARY,
                bg=Colors.WARNING,
            ).pack(side=tk.LEFT, expand=True)

            # Assistant toggle button in banner
            self._toggle_btn = tk.Button(
                banner_content,
                text="Claude",
                font=Fonts.BODY,
                fg=Colors.BG_PRIMARY,
                bg=Colors.ACCENT,
                activebackground=Colors.ACCENT_HOVER,
                activeforeground=Colors.BG_PRIMARY,
                relief=tk.FLAT,
                padx=Theme.spacing.SM,
                pady=2,
                cursor="hand2",
                command=self._toggle_assistant,
            )
            self._toggle_btn.pack(side=tk.RIGHT, padx=Theme.spacing.SM)

        # Content area
        self.content_frame = ttk.Frame(content_wrapper, style="TFrame")
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Assistant pane (right side, initially hidden)
        self._assistant_separator = ttk.Separator(self, orient=tk.VERTICAL)
        self.assistant_pane = AssistantPane(
            self,
            on_send=self._on_assistant_message,
            on_navigate=self._on_navigate,
        )

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

        # Show new screen with comfortable padding
        if screen_name in self._screens:
            self._screens[screen_name].pack(
                fill=tk.BOTH,
                expand=True,
                padx=Theme.spacing.XL,
                pady=Theme.spacing.LG,
            )
            self._current_screen = screen_name
            self.sidebar.set_active(screen_name)

    def _toggle_assistant(self) -> None:
        """Toggle the assistant pane visibility."""
        if self._assistant_visible:
            self._hide_assistant()
        else:
            self._show_assistant()

    def _show_assistant(self) -> None:
        """Show the assistant pane."""
        if not self._assistant_visible:
            self._assistant_separator.pack(side=tk.RIGHT, fill=tk.Y)
            self.assistant_pane.pack(side=tk.RIGHT, fill=tk.Y)
            self._assistant_visible = True
            if hasattr(self, "_toggle_btn"):
                self._toggle_btn.configure(text="Claude")

    def _hide_assistant(self) -> None:
        """Hide the assistant pane."""
        if self._assistant_visible:
            self.assistant_pane.pack_forget()
            self._assistant_separator.pack_forget()
            self._assistant_visible = False
            if hasattr(self, "_toggle_btn"):
                self._toggle_btn.configure(text="Claude")

    def _on_assistant_message(self, message: str) -> None:
        """Handle a message from the user to the assistant.

        Args:
            message: The user's message.
        """
        # For now, just echo back a placeholder response
        # This will be connected to ClaudeService in the next step
        self.assistant_pane.add_assistant_message(
            "I received your message. Claude integration is coming soon!"
        )
