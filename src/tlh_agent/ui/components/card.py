"""Card container component for grouping related content."""

import tkinter as tk

from tlh_agent.ui.theme import Colors, Fonts, Spacing


class Card(tk.Frame):
    """A container with border and optional header for grouping content.

    Provides visual separation and hierarchy in the UI.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str | None = None,
        padding: int = Spacing.MD,
    ) -> None:
        """Initialize the card container.

        Args:
            parent: The parent widget.
            title: Optional title displayed at top of card.
            padding: Internal padding (default: Spacing.MD).
        """
        # Outer frame provides the border
        super().__init__(
            parent,
            bg=Colors.BORDER_LIGHT,
            highlightthickness=0,
        )

        # Inner frame is the actual content area (2px border for visibility)
        self._inner = tk.Frame(self, bg=Colors.BG_SECONDARY)
        self._inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Content frame with padding
        self._content = tk.Frame(self._inner, bg=Colors.BG_SECONDARY)

        if title:
            # Header section
            self._header = tk.Frame(self._inner, bg=Colors.BG_SECONDARY)
            self._header.pack(fill=tk.X, padx=padding, pady=(padding, Spacing.SM))

            self._title_label = tk.Label(
                self._header,
                text=title,
                font=Fonts.SUBHEADING,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
                anchor=tk.W,
            )
            self._title_label.pack(side=tk.LEFT, fill=tk.X)

            # Separator line under header
            separator = tk.Frame(self._inner, bg=Colors.BORDER, height=1)
            separator.pack(fill=tk.X, padx=padding)

            self._content.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        else:
            self._header = None
            self._title_label = None
            self._content.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)

    @property
    def content(self) -> tk.Frame:
        """Get the content frame where child widgets should be added."""
        return self._content

    def set_title(self, title: str) -> None:
        """Update the card title.

        Args:
            title: The new title text.
        """
        if self._title_label:
            self._title_label.configure(text=title)

    def add_header_widget(self, widget_class: type, **kwargs) -> tk.Widget:
        """Add a widget to the header area (right side).

        Args:
            widget_class: The widget class to instantiate.
            **kwargs: Arguments passed to the widget constructor.

        Returns:
            The created widget.
        """
        if self._header is None:
            raise ValueError("Card has no header - create with title parameter")

        widget = widget_class(self._header, **kwargs)
        widget.pack(side=tk.RIGHT)
        return widget


class MetricCard(tk.Frame):
    """A compact card for displaying a single metric with label and value."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        trend: str | None = None,
    ) -> None:
        """Initialize the metric card.

        Args:
            parent: The parent widget.
            label: The metric label.
            value: The metric value.
            trend: Optional trend indicator (e.g., "+5.2%").
        """
        # Outer border frame (lighter for visibility)
        super().__init__(parent, bg=Colors.BORDER_LIGHT)

        # Inner content
        inner = tk.Frame(self, bg=Colors.BG_SECONDARY)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        content = tk.Frame(inner, bg=Colors.BG_SECONDARY)
        content.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.MD)

        # Label
        self._label = tk.Label(
            content,
            text=label,
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self._label.pack(fill=tk.X)

        # Value
        self._value = tk.Label(
            content,
            text=value,
            font=Fonts.HEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self._value.pack(fill=tk.X, pady=(Spacing.XS, 0))

        # Trend
        self._trend = tk.Label(
            content,
            text=trend or "",
            font=Fonts.CAPTION,
            fg=self._get_trend_color(trend),
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self._trend.pack(fill=tk.X)

    def _get_trend_color(self, trend: str | None) -> str:
        """Get color based on trend direction."""
        if not trend:
            return Colors.TEXT_MUTED
        if trend.startswith("+"):
            return Colors.SUCCESS_TEXT
        if trend.startswith("-"):
            return Colors.DANGER_TEXT
        return Colors.TEXT_MUTED

    def set_value(self, value: str, trend: str | None = None) -> None:
        """Update the displayed value and trend.

        Args:
            value: The new value.
            trend: Optional new trend.
        """
        self._value.configure(text=value)
        if trend is not None:
            self._trend.configure(text=trend, fg=self._get_trend_color(trend))
