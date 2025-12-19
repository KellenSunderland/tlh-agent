"""Summary card component for displaying key metrics."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.theme import Colors, Fonts, Sizes, Spacing


class SummaryCard(ttk.Frame):
    """Card component for displaying a metric with optional trend indicator."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        trend: str | None = None,
        trend_positive: bool | None = None,
    ) -> None:
        """Initialize the summary card.

        Args:
            parent: The parent widget.
            label: The label describing the metric.
            value: The current value to display.
            trend: Optional trend indicator (e.g., "+5.2%").
            trend_positive: Whether the trend is positive (green) or negative (red).
        """
        super().__init__(
            parent, style="Card.TFrame", width=Sizes.CARD_MIN_WIDTH, height=Sizes.CARD_HEIGHT
        )
        self.pack_propagate(False)

        self._label = label
        self._trend_positive = trend_positive

        self._setup_ui(label, value, trend)

    def _setup_ui(self, label: str, value: str, trend: str | None) -> None:
        """Set up the card layout.

        Args:
            label: The label text.
            value: The value text.
            trend: Optional trend text.
        """
        # Inner padding frame
        inner = tk.Frame(self, bg=Colors.BG_SECONDARY)
        inner.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.MD)

        # Label (caption style)
        self.label_widget = tk.Label(
            inner,
            text=label,
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.label_widget.pack(fill=tk.X)

        # Value (large, prominent)
        self.value_widget = tk.Label(
            inner,
            text=value,
            font=Fonts.HEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.value_widget.pack(fill=tk.X, pady=(Spacing.XS, 0))

        # Trend indicator (if provided)
        self.trend_widget = tk.Label(
            inner,
            text=trend or "",
            font=Fonts.CAPTION,
            fg=self._get_trend_color(trend),
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.trend_widget.pack(fill=tk.X, pady=(Spacing.XS, 0))

    def _get_trend_color(self, trend: str | None) -> str:
        """Determine trend color based on value.

        Args:
            trend: The trend string.

        Returns:
            The color to use for the trend.
        """
        if not trend:
            return Colors.TEXT_MUTED

        if self._trend_positive is not None:
            return Colors.SUCCESS_TEXT if self._trend_positive else Colors.DANGER_TEXT

        # Auto-detect from string
        if trend.startswith("+"):
            return Colors.SUCCESS_TEXT
        elif trend.startswith("-"):
            return Colors.DANGER_TEXT
        return Colors.TEXT_MUTED

    def set_value(self, value: str, trend: str | None = None) -> None:
        """Update the displayed value and trend.

        Args:
            value: The new value to display.
            trend: Optional new trend indicator.
        """
        self.value_widget.configure(text=value)

        if trend is not None:
            self.trend_widget.configure(text=trend, fg=self._get_trend_color(trend))
