"""Page header component for screen titles."""

import tkinter as tk

from tlh_agent.ui.theme import Colors, Fonts, Spacing


class PageHeader(tk.Frame):
    """A prominent page header with title and optional action buttons.

    Provides consistent, professional header styling across all screens.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str | None = None,
    ) -> None:
        """Initialize the page header.

        Args:
            parent: The parent widget.
            title: The main page title.
            subtitle: Optional subtitle or description.
        """
        super().__init__(parent, bg=Colors.BG_PRIMARY)

        # Left side: title and subtitle
        self._title_section = tk.Frame(self, bg=Colors.BG_PRIMARY)
        self._title_section.pack(side=tk.LEFT, fill=tk.Y)

        # Title with larger, bolder font
        self._title = tk.Label(
            self._title_section,
            text=title,
            font=Fonts.HEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_PRIMARY,
            anchor=tk.W,
        )
        self._title.pack(anchor=tk.W)

        # Subtitle if provided
        if subtitle:
            self._subtitle = tk.Label(
                self._title_section,
                text=subtitle,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_PRIMARY,
                anchor=tk.W,
            )
            self._subtitle.pack(anchor=tk.W)
        else:
            self._subtitle = None

        # Right side: action buttons container
        self._actions = tk.Frame(self, bg=Colors.BG_PRIMARY)
        self._actions.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom border/underline for visual separation
        self._border = tk.Frame(self, bg=Colors.BORDER, height=1)
        self._border.pack(side=tk.BOTTOM, fill=tk.X, pady=(Spacing.MD, 0))

    @property
    def actions(self) -> tk.Frame:
        """Get the actions container for adding buttons."""
        return self._actions

    def add_action_button(
        self,
        text: str,
        command: callable,
        primary: bool = False,
    ) -> tk.Button:
        """Add an action button to the header.

        Args:
            text: Button text.
            command: Click handler.
            primary: If True, uses accent styling.

        Returns:
            The created button.
        """
        if primary:
            btn = tk.Button(
                self._actions,
                text=text,
                font=Fonts.BODY,
                fg=Colors.BG_PRIMARY,
                bg=Colors.ACCENT,
                activebackground=Colors.ACCENT_HOVER,
                activeforeground=Colors.BG_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2",
                padx=Spacing.MD,
                pady=Spacing.XS,
                command=command,
            )
        else:
            btn = tk.Button(
                self._actions,
                text=text,
                font=Fonts.BODY,
                fg="#000000",
                bg=Colors.BG_TERTIARY,
                activebackground=Colors.BORDER_LIGHT,
                activeforeground="#000000",
                relief=tk.FLAT,
                cursor="hand2",
                padx=Spacing.MD,
                pady=Spacing.XS,
                command=command,
            )

        btn.pack(side=tk.LEFT, padx=(Spacing.SM, 0))
        return btn

    def set_title(self, title: str) -> None:
        """Update the title text.

        Args:
            title: New title text.
        """
        self._title.configure(text=title)

    def set_subtitle(self, subtitle: str) -> None:
        """Update the subtitle text.

        Args:
            subtitle: New subtitle text.
        """
        if self._subtitle:
            self._subtitle.configure(text=subtitle)
