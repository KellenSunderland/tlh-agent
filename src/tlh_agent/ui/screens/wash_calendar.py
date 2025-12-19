"""Wash sale calendar screen showing restriction windows."""

import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from tlh_agent.data.mock_data import MockDataFactory, WashSaleRestriction
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class WashCalendarScreen(BaseScreen):
    """Screen showing visual calendar of wash sale restriction windows."""

    def _setup_ui(self) -> None:
        """Set up the wash calendar layout."""
        # Header
        header = PageHeader(self, title="Wash Sale Calendar", subtitle="61-day restriction windows")
        header.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Main content - two column layout
        content_frame = ttk.Frame(self, style="TFrame")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left: Calendar
        calendar_frame = tk.Frame(content_frame, bg=Colors.BG_SECONDARY)
        calendar_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, Spacing.MD))

        # Calendar navigation
        nav_frame = tk.Frame(calendar_frame, bg=Colors.BG_SECONDARY)
        nav_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        self.prev_btn = tk.Button(
            nav_frame,
            text="<",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            relief=tk.FLAT,
            width=3,
            cursor="hand2",
            command=self._prev_month,
        )
        self.prev_btn.pack(side=tk.LEFT)

        self.month_label = tk.Label(
            nav_frame,
            text="",
            font=Fonts.SUBHEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
        )
        self.month_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(
            nav_frame,
            text=">",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            relief=tk.FLAT,
            width=3,
            cursor="hand2",
            command=self._next_month,
        )
        self.next_btn.pack(side=tk.RIGHT)

        # Calendar grid
        self.calendar_grid = tk.Frame(calendar_frame, bg=Colors.BG_SECONDARY)
        self.calendar_grid.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.SM)

        # Legend
        legend_frame = tk.Frame(calendar_frame, bg=Colors.BG_SECONDARY)
        legend_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        for color, label in [
            (Colors.WARNING, "Restriction Active"),
            (Colors.DANGER, "Sale Date"),
            (Colors.SUCCESS, "Restriction Ends"),
        ]:
            item = tk.Frame(legend_frame, bg=Colors.BG_SECONDARY)
            item.pack(side=tk.LEFT, padx=(0, Spacing.LG))

            tk.Frame(item, bg=color, width=16, height=16).pack(side=tk.LEFT, padx=(0, Spacing.XS))
            tk.Label(
                item,
                text=label,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_SECONDARY,
                bg=Colors.BG_SECONDARY,
            ).pack(side=tk.LEFT)

        # Right: Restrictions list
        list_frame = tk.Frame(content_frame, bg=Colors.BG_SECONDARY, width=280)
        list_frame.pack(side=tk.RIGHT, fill=tk.Y)
        list_frame.pack_propagate(False)

        list_header = tk.Label(
            list_frame,
            text="Active Restrictions",
            font=Fonts.SUBHEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
        )
        list_header.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        self.restrictions_list = tk.Frame(list_frame, bg=Colors.BG_SECONDARY)
        self.restrictions_list.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD)

        # Initialize current month
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self._restrictions: list[WashSaleRestriction] = []

    def refresh(self) -> None:
        """Refresh wash sale calendar data."""
        self._restrictions = MockDataFactory.get_active_wash_sale_restrictions()
        self._build_calendar()
        self._build_restrictions_list()

    def _build_calendar(self) -> None:
        """Build the calendar grid for the current month."""
        # Clear existing
        for widget in self.calendar_grid.winfo_children():
            widget.destroy()

        # Update month label
        month_name = calendar.month_name[self.current_month]
        self.month_label.configure(text=f"{month_name} {self.current_year}")

        # Day headers
        header_row = tk.Frame(self.calendar_grid, bg=Colors.BG_SECONDARY)
        header_row.pack(fill=tk.X)

        for day in ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]:
            tk.Label(
                header_row,
                text=day,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
                width=4,
            ).pack(side=tk.LEFT, padx=2)

        # Get calendar data
        cal = calendar.monthcalendar(self.current_year, self.current_month)

        # Build calendar rows
        today = date.today()
        for week in cal:
            week_row = tk.Frame(self.calendar_grid, bg=Colors.BG_SECONDARY)
            week_row.pack(fill=tk.X, pady=1)

            for day_num in week:
                if day_num == 0:
                    # Empty cell
                    tk.Label(
                        week_row,
                        text="",
                        font=Fonts.BODY,
                        bg=Colors.BG_SECONDARY,
                        width=4,
                        height=2,
                    ).pack(side=tk.LEFT, padx=2)
                else:
                    current_date = date(self.current_year, self.current_month, day_num)
                    bg_color, fg_color = self._get_day_colors(current_date, today)

                    day_label = tk.Label(
                        week_row,
                        text=str(day_num),
                        font=Fonts.BODY,
                        fg=fg_color,
                        bg=bg_color,
                        width=4,
                        height=2,
                    )
                    day_label.pack(side=tk.LEFT, padx=2)

    def _get_day_colors(self, check_date: date, today: date) -> tuple[str, str]:
        """Get background and foreground colors for a calendar day.

        Args:
            check_date: The date to check.
            today: Today's date.

        Returns:
            Tuple of (background_color, foreground_color).
        """
        bg = Colors.BG_SECONDARY
        fg = Colors.TEXT_PRIMARY

        # Check if today
        if check_date == today:
            fg = Colors.ACCENT

        # Check restrictions
        for restriction in self._restrictions:
            if check_date == restriction.sale_date:
                bg = Colors.DANGER
                fg = Colors.TEXT_PRIMARY
                break
            elif check_date == restriction.restriction_end:
                bg = Colors.SUCCESS
                fg = Colors.TEXT_PRIMARY
                break
            elif restriction.restriction_start <= check_date <= restriction.restriction_end:
                bg = Colors.WARNING
                fg = Colors.BG_PRIMARY
                break

        return bg, fg

    def _build_restrictions_list(self) -> None:
        """Build the restrictions list panel."""
        # Clear existing
        for widget in self.restrictions_list.winfo_children():
            widget.destroy()

        active = [r for r in self._restrictions if r.status == "active"]
        expired = [r for r in self._restrictions if r.status == "expired"]

        if not active and not expired:
            tk.Label(
                self.restrictions_list,
                text="No wash sale restrictions",
                font=Fonts.BODY,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(pady=Spacing.MD)
            return

        # Active restrictions
        for restriction in active:
            self._build_restriction_card(restriction, active=True)

        # Separator
        if active and expired:
            tk.Frame(self.restrictions_list, bg=Colors.BORDER, height=1).pack(
                fill=tk.X, pady=Spacing.SM
            )

            tk.Label(
                self.restrictions_list,
                text="Recently Expired",
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(anchor=tk.W, pady=(Spacing.XS, Spacing.SM))

        # Expired restrictions
        for restriction in expired:
            self._build_restriction_card(restriction, active=False)

    def _build_restriction_card(self, restriction: WashSaleRestriction, active: bool) -> None:
        """Build a restriction card.

        Args:
            restriction: The wash sale restriction.
            active: Whether the restriction is active.
        """
        card = tk.Frame(self.restrictions_list, bg=Colors.BG_TERTIARY)
        card.pack(fill=tk.X, pady=2)

        inner = tk.Frame(card, bg=Colors.BG_TERTIARY)
        inner.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.SM)

        # Ticker
        tk.Label(
            inner,
            text=restriction.ticker,
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY if active else Colors.TEXT_MUTED,
            bg=Colors.BG_TERTIARY,
        ).pack(anchor=tk.W)

        # Sale date
        tk.Label(
            inner,
            text=f"Sold: {restriction.sale_date}",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_TERTIARY,
        ).pack(anchor=tk.W)

        # Status
        if active:
            days = restriction.days_remaining
            status_text = f"Clear: {restriction.restriction_end} ({days} days)"
            status_color = Colors.WARNING
        else:
            status_text = f"Cleared: {restriction.restriction_end}"
            status_color = Colors.TEXT_MUTED

        tk.Label(
            inner,
            text=status_text,
            font=Fonts.CAPTION,
            fg=status_color,
            bg=Colors.BG_TERTIARY,
        ).pack(anchor=tk.W)

    def _prev_month(self) -> None:
        """Navigate to previous month."""
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._build_calendar()

    def _next_month(self) -> None:
        """Navigate to next month."""
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._build_calendar()
