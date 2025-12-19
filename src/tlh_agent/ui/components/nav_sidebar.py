"""Navigation sidebar component."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import ClassVar

from tlh_agent.ui.theme import Colors, Fonts, Sizes, Spacing


class NavSidebar(ttk.Frame):
    """Sidebar with navigation buttons for each screen."""

    NAV_ITEMS: ClassVar[list[tuple[str, str]]] = [
        ("dashboard", "Dashboard"),
        ("positions", "Positions"),
        ("harvest", "Harvest Queue"),
        ("wash_sales", "Wash Sales"),
        ("history", "Trade History"),
        ("ledger", "Loss Ledger"),
        ("settings", "Settings"),
    ]

    def __init__(self, parent: tk.Widget, on_navigate: Callable[[str], None]) -> None:
        """Initialize the navigation sidebar.

        Args:
            parent: The parent widget.
            on_navigate: Callback function when a nav item is clicked.
        """
        super().__init__(parent, style="Sidebar.TFrame", width=Sizes.SIDEBAR_WIDTH)
        self.pack_propagate(False)  # Maintain fixed width

        self._on_navigate = on_navigate
        self._buttons: dict[str, tk.Frame] = {}
        self._active_screen: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the sidebar layout."""
        # App title/logo area
        title_frame = ttk.Frame(self, style="Sidebar.TFrame")
        title_frame.pack(fill=tk.X, pady=(Spacing.LG, Spacing.XL))

        title_label = ttk.Label(
            title_frame,
            text="TLH Agent",
            style="Subheading.TLabel",
        )
        title_label.configure(background=Colors.BG_SECONDARY)
        title_label.pack(padx=Spacing.MD)

        # Navigation items
        nav_frame = ttk.Frame(self, style="Sidebar.TFrame")
        nav_frame.pack(fill=tk.BOTH, expand=True)

        for screen_id, label in self.NAV_ITEMS:
            btn = self._create_nav_button(nav_frame, screen_id, label)
            self._buttons[screen_id] = btn

    def _create_nav_button(self, parent: ttk.Frame, screen_id: str, label: str) -> tk.Frame:
        """Create a navigation button.

        Args:
            parent: The parent frame.
            screen_id: The identifier for the screen.
            label: The display text for the button.

        Returns:
            The created button widget.
        """
        # Use a frame to create a custom styled button
        btn_frame = tk.Frame(
            parent,
            bg=Colors.BG_SECONDARY,
            height=Sizes.NAV_ITEM_HEIGHT,
            cursor="hand2",
        )
        btn_frame.pack(fill=tk.X, padx=Spacing.SM, pady=2)
        btn_frame.pack_propagate(False)

        label_widget = tk.Label(
            btn_frame,
            text=f"  {label}",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_SECONDARY,
            anchor="w",
            cursor="hand2",
        )
        label_widget.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM)

        # Bind click events
        for widget in (btn_frame, label_widget):
            widget.bind("<Button-1>", lambda e, sid=screen_id: self._on_click(sid))
            widget.bind(
                "<Enter>", lambda e, frm=btn_frame, lbl=label_widget: self._on_hover(frm, lbl)
            )
            widget.bind(
                "<Leave>",
                lambda e, frm=btn_frame, lbl=label_widget, sid=screen_id: self._on_leave(
                    frm, lbl, sid
                ),
            )

        # Store references for state management
        btn_frame.label = label_widget  # type: ignore[attr-defined]

        return btn_frame

    def _on_click(self, screen_id: str) -> None:
        """Handle navigation button click.

        Args:
            screen_id: The screen to navigate to.
        """
        self._on_navigate(screen_id)

    def _on_hover(self, frame: tk.Frame, label: tk.Label) -> None:
        """Handle mouse hover enter.

        Args:
            frame: The button frame.
            label: The label widget.
        """
        frame.configure(bg=Colors.BG_TERTIARY)
        label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)

    def _on_leave(self, frame: tk.Frame, label: tk.Label, screen_id: str) -> None:
        """Handle mouse hover leave.

        Args:
            frame: The button frame.
            label: The label widget.
            screen_id: The screen identifier for this button.
        """
        if screen_id == self._active_screen:
            frame.configure(bg=Colors.BG_TERTIARY)
            label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)
        else:
            frame.configure(bg=Colors.BG_SECONDARY)
            label.configure(bg=Colors.BG_SECONDARY, fg=Colors.TEXT_SECONDARY)

    def set_active(self, screen_id: str) -> None:
        """Set the active navigation item.

        Args:
            screen_id: The screen to mark as active.
        """
        # Reset previous active
        if self._active_screen and self._active_screen in self._buttons:
            prev_btn = self._buttons[self._active_screen]
            prev_btn.configure(bg=Colors.BG_SECONDARY)
            prev_btn.label.configure(bg=Colors.BG_SECONDARY, fg=Colors.TEXT_SECONDARY)  # type: ignore[attr-defined]

        # Set new active
        self._active_screen = screen_id
        if screen_id in self._buttons:
            btn = self._buttons[screen_id]
            btn.configure(bg=Colors.BG_TERTIARY)
            btn.label.configure(bg=Colors.BG_TERTIARY, fg=Colors.TEXT_PRIMARY)  # type: ignore[attr-defined]
