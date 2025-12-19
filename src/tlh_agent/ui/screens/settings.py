"""Settings screen for configuring the application."""

import tkinter as tk
from tkinter import ttk

from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class SettingsScreen(BaseScreen):
    """Screen for configuring application settings."""

    def _setup_ui(self) -> None:
        """Set up the settings layout."""
        # Header
        header = PageHeader(
            self, title="Settings", subtitle="Configure harvesting rules and preferences"
        )
        header.pack(fill=tk.X, pady=(0, Spacing.LG))
        header.add_action_button("Reset", self._on_reset)
        header.add_action_button("Save", self._on_save, primary=True)

        # Scrollable settings area
        canvas = tk.Canvas(self, bg=Colors.BG_PRIMARY, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        self.settings_frame = tk.Frame(canvas, bg=Colors.BG_PRIMARY)

        self.settings_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.settings_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build settings sections
        self._build_scanner_settings()
        self._build_rebuy_settings()
        self._build_rules_settings()
        self._build_wash_sale_settings()
        self._build_brokerage_settings()

    def _build_section(self, title: str) -> tk.Frame:
        """Build a settings section with title.

        Args:
            title: The section title.

        Returns:
            The content frame for the section.
        """
        section_card = Card(self.settings_frame, title=title)
        section_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        return section_card.content

    def _build_field(
        self,
        parent: tk.Frame,
        label: str,
        widget_type: str = "entry",
        options: list[str] | None = None,
        default: str = "",
        width: int = 20,
    ) -> tk.Variable:
        """Build a settings field.

        Args:
            parent: Parent frame.
            label: Field label.
            widget_type: Type of widget (entry, dropdown, checkbox).
            options: Options for dropdown.
            default: Default value.
            width: Widget width.

        Returns:
            The variable holding the field value.
        """
        row = tk.Frame(parent, bg=Colors.BG_SECONDARY)
        row.pack(fill=tk.X, pady=2)

        tk.Label(
            row,
            text=label,
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            width=25,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        if widget_type == "entry":
            var = tk.StringVar(value=default)
            ttk.Entry(row, textvariable=var, width=width).pack(side=tk.LEFT)
        elif widget_type == "dropdown":
            var = tk.StringVar(value=default)
            dropdown = ttk.Combobox(
                row, textvariable=var, values=options or [], state="readonly", width=width - 2
            )
            dropdown.pack(side=tk.LEFT)
        elif widget_type == "checkbox":
            var = tk.BooleanVar(value=default == "True")
            ttk.Checkbutton(row, variable=var).pack(side=tk.LEFT)
        else:
            var = tk.StringVar(value=default)

        return var

    def _build_scanner_settings(self) -> None:
        """Build scanner settings section."""
        content = self._build_section("Scanner")

        self.scan_frequency = self._build_field(
            content,
            "Frequency:",
            widget_type="dropdown",
            options=["Daily", "Weekly", "Monthly"],
            default="Daily",
        )

        self.scan_day = self._build_field(
            content,
            "Weekly Scan Day:",
            widget_type="dropdown",
            options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            default="Friday",
        )

        self.scan_time = self._build_field(
            content,
            "Scan Time (24h):",
            default="10:30",
            width=10,
        )

    def _build_rebuy_settings(self) -> None:
        """Build rebuy strategy settings section."""
        content = self._build_section("Rebuy Strategy")

        self.rebuy_strategy = self._build_field(
            content,
            "Strategy:",
            widget_type="dropdown",
            options=["Wait", "Swap", "Hybrid"],
            default="Swap",
        )

        self.wait_days = self._build_field(
            content,
            "Wait Days:",
            default="31",
            width=10,
        )

        self.swap_back_enabled = self._build_field(
            content,
            "Swap Back Enabled:",
            widget_type="checkbox",
            default="True",
        )

        self.swap_back_days = self._build_field(
            content,
            "Swap Back After Days:",
            default="32",
            width=10,
        )

        self.hybrid_threshold = self._build_field(
            content,
            "Hybrid Threshold ($):",
            default="5000",
            width=10,
        )

    def _build_rules_settings(self) -> None:
        """Build rules engine settings section."""
        content = self._build_section("Rules Engine")

        self.min_loss_usd = self._build_field(
            content,
            "Min Loss ($):",
            default="100",
            width=10,
        )

        self.min_loss_pct = self._build_field(
            content,
            "Min Loss (%):",
            default="3.0",
            width=10,
        )

        self.min_tax_benefit = self._build_field(
            content,
            "Min Tax Benefit ($):",
            default="50",
            width=10,
        )

        self.tax_rate = self._build_field(
            content,
            "Assumed Tax Rate (%):",
            default="35",
            width=10,
        )

        self.prefer_short_term = self._build_field(
            content,
            "Prefer Short-Term:",
            widget_type="checkbox",
            default="True",
        )

        self.min_holding_days = self._build_field(
            content,
            "Min Holding Days:",
            default="7",
            width=10,
        )

        self.max_harvest_pct = self._build_field(
            content,
            "Max Harvest Per Scan (%):",
            default="10.0",
            width=10,
        )

    def _build_wash_sale_settings(self) -> None:
        """Build wash sale settings section."""
        content = self._build_section("Wash Sale Tracking")

        self.wash_window_days = self._build_field(
            content,
            "Window Days:",
            default="30",
            width=10,
        )

        self.track_external = self._build_field(
            content,
            "Track External Accounts:",
            widget_type="checkbox",
            default="True",
        )

        self.warn_violations = self._build_field(
            content,
            "Warn on Violations:",
            widget_type="checkbox",
            default="True",
        )

    def _build_brokerage_settings(self) -> None:
        """Build brokerage settings section."""
        content = self._build_section("Brokerage")

        self.broker_provider = self._build_field(
            content,
            "Provider:",
            widget_type="dropdown",
            options=["Robinhood (Manual)", "Alpaca (API)"],
            default="Alpaca (API)",
        )

        self.paper_trading = self._build_field(
            content,
            "Paper Trading:",
            widget_type="checkbox",
            default="True",
        )

        self.order_type = self._build_field(
            content,
            "Order Type:",
            widget_type="dropdown",
            options=["Market", "Limit"],
            default="Limit",
        )

        self.limit_buffer = self._build_field(
            content,
            "Limit Price Buffer (%):",
            default="0.1",
            width=10,
        )

        self.require_confirm = self._build_field(
            content,
            "Require Confirmation:",
            widget_type="checkbox",
            default="False",
        )

    def refresh(self) -> None:
        """Refresh settings data."""
        # Would load from config file
        pass

    def _on_save(self) -> None:
        """Save settings."""
        # Would save to config file
        pass

    def _on_reset(self) -> None:
        """Reset settings to defaults."""
        # Would reset all fields to default values
        pass
