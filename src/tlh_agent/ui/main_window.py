"""Main window with sidebar navigation and content area."""

import logging
import tkinter as tk
from tkinter import ttk

from tlh_agent.credentials import get_claude_api_key, has_claude_api_key
from tlh_agent.services import get_provider
from tlh_agent.services.assistant import AssistantController, AssistantState
from tlh_agent.services.claude import ClaudeService
from tlh_agent.services.claude_tools import ClaudeToolProvider
from tlh_agent.services.index import IndexService
from tlh_agent.services.rebalance import RebalanceService
from tlh_agent.services.trade_queue import TradeQueueService
from tlh_agent.ui.components.assistant_pane import AssistantPane
from tlh_agent.ui.components.nav_sidebar import NavSidebar
from tlh_agent.ui.theme import Colors, Fonts, Theme

logger = logging.getLogger(__name__)


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
        self._assistant_controller: AssistantController | None = None
        self._trade_queue = TradeQueueService()
        self._streaming_text: str = ""

        self._setup_ui()
        self._setup_assistant()

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

    def _setup_assistant(self) -> None:
        """Set up the Claude assistant controller."""
        if not has_claude_api_key():
            logger.info("Claude API key not configured")
            return

        try:
            api_key = get_claude_api_key()
            if not api_key:
                return

            provider = get_provider()

            # Create Claude service
            claude_service = ClaudeService(api_key=api_key)

            # Create index service (for S&P 500 tracking)
            index_service = IndexService()

            # Create rebalance service if portfolio is available
            rebalance_service = None
            if provider.portfolio:
                rebalance_service = RebalanceService(
                    portfolio_service=provider.portfolio,
                    index_service=index_service,
                    wash_sale_service=provider.wash_sale,
                )

            # Create tool provider with all services
            tool_provider = ClaudeToolProvider(
                portfolio_service=provider.portfolio,
                scanner=provider.scanner,
                index_service=index_service,
                rebalance_service=rebalance_service,
                trade_queue=self._trade_queue,
            )

            # Create assistant controller
            self._assistant_controller = AssistantController(
                claude_service=claude_service,
                tool_provider=tool_provider,
            )

            # Set up callbacks for UI updates
            self._assistant_controller.set_callbacks(
                on_text=self._on_assistant_text,
                on_tool_use=self._on_assistant_tool_use,
                on_tool_done=self._on_assistant_tool_done,
                on_done=self._on_assistant_done,
                on_error=self._on_assistant_error,
                on_state_change=self._on_assistant_state_change,
            )

            logger.info("Claude assistant initialized successfully")

        except Exception:
            logger.exception("Failed to initialize Claude assistant")
            self._assistant_controller = None

    def _on_assistant_message(self, message: str) -> None:
        """Handle a message from the user to the assistant.

        Args:
            message: The user's message.
        """
        if not self._assistant_controller:
            self.assistant_pane.add_assistant_message(
                "Claude is not configured. Please add your API key in Settings."
            )
            return

        # Disable input while processing
        self.assistant_pane.set_enabled(False)

        # Start streaming message
        self._streaming_text = ""
        self.assistant_pane.start_streaming_message("")

        # Send message to Claude
        self._assistant_controller.send_message(message)

    def _on_assistant_text(self, text: str) -> None:
        """Handle streaming text from Claude.

        Args:
            text: Text chunk from Claude.
        """
        self._streaming_text += text
        # Update UI from main thread
        self.after(0, lambda: self.assistant_pane.update_streaming_message(
            self._streaming_text
        ))

    def _on_assistant_tool_use(self, tool_name: str) -> None:
        """Handle tool use start.

        Args:
            tool_name: Name of the tool being used.
        """
        # Add tool use indicator
        self.after(0, lambda: self.assistant_pane.add_tool_use(tool_name))

    def _on_assistant_tool_done(self, tool_name: str, success: bool) -> None:
        """Handle tool execution completion.

        Args:
            tool_name: Name of the tool.
            success: Whether the tool succeeded.
        """
        # The tool use message is already showing, we could update its status
        # For now, just log it
        logger.debug(f"Tool {tool_name} completed: {'success' if success else 'error'}")

    def _on_assistant_done(self) -> None:
        """Handle assistant response completion."""
        def _finish():
            self.assistant_pane.finish_streaming_message()
            self.assistant_pane.set_enabled(True)

            # If trades were proposed, add a button to view the queue
            if self._trade_queue.get_all_trades():
                self.assistant_pane.add_action_button("View Trade Queue", "harvest")

        self.after(0, _finish)

    def _on_assistant_error(self, error: str) -> None:
        """Handle assistant error.

        Args:
            error: Error message.
        """
        def _show_error():
            self.assistant_pane.finish_streaming_message()
            self.assistant_pane.add_assistant_message(f"Error: {error}")
            self.assistant_pane.set_enabled(True)

        self.after(0, _show_error)

    def _on_assistant_state_change(self, state: AssistantState) -> None:
        """Handle assistant state change.

        Args:
            state: New assistant state.
        """
        # Could update UI based on state (e.g., show processing indicator)
        pass
