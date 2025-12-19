"""Navigation sidebar component."""

import tkinter as tk
from collections.abc import Callable
from typing import ClassVar

from tlh_agent.ui.theme import Colors, Fonts, Sizes, Spacing


class NavSidebar(tk.Frame):
    """Sidebar with navigation buttons for each screen."""

    NAV_ITEMS: ClassVar[list[tuple[str, str, str]]] = [
        ("dashboard", "Dashboard", "📊"),
        ("positions", "Positions", "📈"),
        ("harvest", "Harvest Queue", "🌾"),
        ("wash_sales", "Wash Sales", "📅"),
        ("history", "Trade History", "📋"),
        ("ledger", "Loss Ledger", "📒"),
        ("settings", "Settings", "⚙️"),
    ]

    def __init__(self, parent: tk.Widget, on_navigate: Callable[[str], None]) -> None:
        """Initialize the navigation sidebar.

        Args:
            parent: The parent widget.
            on_navigate: Callback function when a nav item is clicked.
        """
        # Main frame with border on right side
        super().__init__(parent, bg=Colors.BG_SECONDARY, width=Sizes.SIDEBAR_WIDTH)
        self.pack_propagate(False)

        self._on_navigate = on_navigate
        self._buttons: dict[str, tk.Frame] = {}
        self._active_screen: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the sidebar layout."""
        # App title/logo area with bottom border
        title_frame = tk.Frame(self, bg=Colors.BG_SECONDARY)
        title_frame.pack(fill=tk.X, pady=(Spacing.LG, 0))

        title_label = tk.Label(
            title_frame,
            text="TLH Agent",
            font=Fonts.HEADING,
            fg=Colors.ACCENT,
            bg=Colors.BG_SECONDARY,
        )
        title_label.pack(padx=Spacing.MD, pady=(0, Spacing.MD))

        # Separator under title
        separator = tk.Frame(self, bg=Colors.BORDER, height=1)
        separator.pack(fill=tk.X, padx=Spacing.MD)

        # Navigation items
        nav_frame = tk.Frame(self, bg=Colors.BG_SECONDARY)
        nav_frame.pack(fill=tk.BOTH, expand=True, pady=(Spacing.MD, 0))

        for screen_id, label, icon in self.NAV_ITEMS:
            btn = self._create_nav_button(nav_frame, screen_id, label, icon)
            self._buttons[screen_id] = btn

        # Right border (visual separator from content)
        border_frame = tk.Frame(self, bg=Colors.BORDER, width=1)
        border_frame.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_nav_button(
        self, parent: tk.Frame, screen_id: str, label: str, icon: str
    ) -> tk.Frame:
        """Create a navigation button with accent indicator.

        Args:
            parent: The parent frame.
            screen_id: The identifier for the screen.
            label: The display text for the button.
            icon: The emoji icon for the button.

        Returns:
            The created button frame.
        """
        # Container for the button row
        btn_container = tk.Frame(parent, bg=Colors.BG_SECONDARY)
        btn_container.pack(fill=tk.X, pady=1)

        # Accent bar (left edge indicator for active state)
        accent_bar = tk.Frame(
            btn_container,
            bg=Colors.BG_SECONDARY,  # Hidden by default
            width=3,
        )
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        # Button content frame
        btn_frame = tk.Frame(
            btn_container,
            bg=Colors.BG_SECONDARY,
            height=Sizes.NAV_ITEM_HEIGHT,
            cursor="hand2",
        )
        btn_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        btn_frame.pack_propagate(False)

        # Icon and label in horizontal layout
        content_frame = tk.Frame(btn_frame, bg=Colors.BG_SECONDARY)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD)

        icon_label = tk.Label(
            content_frame,
            text=icon,
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            cursor="hand2",
        )
        icon_label.pack(side=tk.LEFT, pady=Spacing.SM)

        text_label = tk.Label(
            content_frame,
            text=label,
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
            anchor="w",
            cursor="hand2",
        )
        text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(Spacing.SM, 0))

        # Bind click events to all interactive elements
        clickable = [btn_container, btn_frame, content_frame, icon_label, text_label]

        def make_hover_handler(c, b, cf, i, t, a):
            return lambda e: self._on_hover(c, b, cf, i, t, a)

        def make_leave_handler(c, b, cf, i, t, a, sid):
            return lambda e: self._on_leave(c, b, cf, i, t, a, sid)

        for widget in clickable:
            widget.bind("<Button-1>", lambda e, sid=screen_id: self._on_click(sid))
            widget.bind(
                "<Enter>",
                make_hover_handler(
                    btn_container, btn_frame, content_frame, icon_label, text_label, accent_bar
                ),
            )
            widget.bind(
                "<Leave>",
                make_leave_handler(
                    btn_container, btn_frame, content_frame, icon_label, text_label, accent_bar,
                    screen_id
                ),
            )

        # Store references for state management
        btn_container.accent_bar = accent_bar  # type: ignore[attr-defined]
        btn_container.btn_frame = btn_frame  # type: ignore[attr-defined]
        btn_container.content_frame = content_frame  # type: ignore[attr-defined]
        btn_container.icon_label = icon_label  # type: ignore[attr-defined]
        btn_container.text_label = text_label  # type: ignore[attr-defined]

        return btn_container

    def _on_click(self, screen_id: str) -> None:
        """Handle navigation button click."""
        self._on_navigate(screen_id)

    def _on_hover(
        self,
        container: tk.Frame,
        btn_frame: tk.Frame,
        content_frame: tk.Frame,
        icon_label: tk.Label,
        text_label: tk.Label,
        accent_bar: tk.Frame,
    ) -> None:
        """Handle mouse hover enter."""
        container.configure(bg=Colors.BG_TERTIARY)
        btn_frame.configure(bg=Colors.BG_TERTIARY)
        content_frame.configure(bg=Colors.BG_TERTIARY)
        icon_label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)
        text_label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)

    def _on_leave(
        self,
        container: tk.Frame,
        btn_frame: tk.Frame,
        content_frame: tk.Frame,
        icon_label: tk.Label,
        text_label: tk.Label,
        accent_bar: tk.Frame,
        screen_id: str,
    ) -> None:
        """Handle mouse hover leave."""
        if screen_id == self._active_screen:
            self._apply_active_style(
                container, btn_frame, content_frame, icon_label, text_label, accent_bar
            )
        else:
            self._apply_inactive_style(
                container, btn_frame, content_frame, icon_label, text_label, accent_bar
            )

    def _apply_active_style(
        self,
        container: tk.Frame,
        btn_frame: tk.Frame,
        content_frame: tk.Frame,
        icon_label: tk.Label,
        text_label: tk.Label,
        accent_bar: tk.Frame,
    ) -> None:
        """Apply active/selected styling to a nav item."""
        container.configure(bg=Colors.BG_TERTIARY)
        btn_frame.configure(bg=Colors.BG_TERTIARY)
        content_frame.configure(bg=Colors.BG_TERTIARY)
        icon_label.configure(bg=Colors.BG_TERTIARY, fg=Colors.ACCENT)
        text_label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)
        accent_bar.configure(bg=Colors.ACCENT)

    def _apply_inactive_style(
        self,
        container: tk.Frame,
        btn_frame: tk.Frame,
        content_frame: tk.Frame,
        icon_label: tk.Label,
        text_label: tk.Label,
        accent_bar: tk.Frame,
    ) -> None:
        """Apply inactive styling to a nav item."""
        container.configure(bg=Colors.BG_SECONDARY)
        btn_frame.configure(bg=Colors.BG_SECONDARY)
        content_frame.configure(bg=Colors.BG_SECONDARY)
        icon_label.configure(bg=Colors.BG_SECONDARY, fg=Colors.TEXT_MUTED)
        text_label.configure(bg=Colors.BG_SECONDARY, fg=Colors.TEXT_SECONDARY)
        accent_bar.configure(bg=Colors.BG_SECONDARY)

    def set_active(self, screen_id: str) -> None:
        """Set the active navigation item.

        Args:
            screen_id: The screen to mark as active.
        """
        # Reset previous active
        if self._active_screen and self._active_screen in self._buttons:
            prev = self._buttons[self._active_screen]
            self._apply_inactive_style(
                prev,
                prev.btn_frame,  # type: ignore[attr-defined]
                prev.content_frame,  # type: ignore[attr-defined]
                prev.icon_label,  # type: ignore[attr-defined]
                prev.text_label,  # type: ignore[attr-defined]
                prev.accent_bar,  # type: ignore[attr-defined]
            )

        # Set new active
        self._active_screen = screen_id
        if screen_id in self._buttons:
            btn = self._buttons[screen_id]
            self._apply_active_style(
                btn,
                btn.btn_frame,  # type: ignore[attr-defined]
                btn.content_frame,  # type: ignore[attr-defined]
                btn.icon_label,  # type: ignore[attr-defined]
                btn.text_label,  # type: ignore[attr-defined]
                btn.accent_bar,  # type: ignore[attr-defined]
            )
