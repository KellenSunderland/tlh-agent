"""Settings screen for configuring the application."""

import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, ttk

from tlh_agent.credentials import (
    delete_claude_api_key,
    get_claude_api_key,
    has_claude_api_key,
    set_claude_api_key,
)
from tlh_agent.services import get_provider
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
        self._build_claude_settings()
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

    def _build_claude_settings(self) -> None:
        """Build Claude AI settings section."""
        content = self._build_section("Claude AI Assistant")

        # API Key field (password style)
        row = tk.Frame(content, bg=Colors.BG_SECONDARY)
        row.pack(fill=tk.X, pady=2)

        tk.Label(
            row,
            text="API Key:",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            width=25,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        self.claude_api_key = tk.StringVar()
        self.claude_api_entry = ttk.Entry(row, textvariable=self.claude_api_key, width=30, show="•")
        self.claude_api_entry.pack(side=tk.LEFT)

        # Show/Hide toggle
        self._api_key_visible = False
        self.toggle_btn = tk.Button(
            row,
            text="Show",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            activebackground=Colors.BG_TERTIARY,
            relief=tk.FLAT,
            command=self._toggle_api_key_visibility,
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=Spacing.XS)

        # Model selection
        self.claude_model = self._build_field(
            content,
            "Model:",
            widget_type="dropdown",
            options=[
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-haiku-20240307",
            ],
            default="claude-sonnet-4-20250514",
        )

        # Status indicator
        status_row = tk.Frame(content, bg=Colors.BG_SECONDARY)
        status_row.pack(fill=tk.X, pady=2)

        tk.Label(
            status_row,
            text="Status:",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
            width=25,
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        self.claude_status = tk.Label(
            status_row,
            text="Not configured",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
        )
        self.claude_status.pack(side=tk.LEFT)

        # Buttons row
        buttons_row = tk.Frame(content, bg=Colors.BG_SECONDARY)
        buttons_row.pack(fill=tk.X, pady=(Spacing.SM, 0))

        # Spacer to align with other fields
        tk.Label(
            buttons_row,
            text="",
            font=Fonts.BODY,
            bg=Colors.BG_SECONDARY,
            width=25,
        ).pack(side=tk.LEFT)

        self.save_api_btn = tk.Button(
            buttons_row,
            text="Save API Key",
            font=Fonts.BODY,
            fg=Colors.BG_PRIMARY,
            bg=Colors.ACCENT,
            activebackground=Colors.ACCENT_HOVER,
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.SM,
            pady=Spacing.XS,
            command=self._save_claude_api_key,
        )
        self.save_api_btn.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        self.test_btn = tk.Button(
            buttons_row,
            text="Test Connection",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BG_SECONDARY,
            relief=tk.FLAT,
            padx=Spacing.SM,
            pady=Spacing.XS,
            command=self._test_claude_connection,
        )
        self.test_btn.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        self.clear_api_btn = tk.Button(
            buttons_row,
            text="Clear",
            font=Fonts.BODY,
            fg=Colors.DANGER_TEXT,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BG_SECONDARY,
            relief=tk.FLAT,
            padx=Spacing.SM,
            pady=Spacing.XS,
            command=self._clear_claude_api_key,
        )
        self.clear_api_btn.pack(side=tk.LEFT)

        # Load current status
        self._update_claude_status()

    def _toggle_api_key_visibility(self) -> None:
        """Toggle API key visibility."""
        self._api_key_visible = not self._api_key_visible
        if self._api_key_visible:
            self.claude_api_entry.configure(show="")
            self.toggle_btn.configure(text="Hide")
        else:
            self.claude_api_entry.configure(show="•")
            self.toggle_btn.configure(text="Show")

    def _update_claude_status(self) -> None:
        """Update Claude status indicator."""
        if has_claude_api_key():
            self.claude_status.configure(text="Configured ✓", fg=Colors.SUCCESS_TEXT)
            # Show masked key
            key = get_claude_api_key()
            if key:
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
                self.claude_api_key.set(masked)
        else:
            self.claude_status.configure(text="Not configured", fg=Colors.TEXT_MUTED)
            self.claude_api_key.set("")

    def _save_claude_api_key(self) -> None:
        """Save Claude API key to keychain."""
        key = self.claude_api_key.get().strip()

        # Check if it's a masked key (user didn't change it)
        if "..." in key:
            messagebox.showinfo("Info", "Enter a new API key to save.")
            return

        if not key or not key.startswith("sk-"):
            messagebox.showerror(
                "Error", "Invalid API key format. Key should start with 'sk-'"
            )
            return

        set_claude_api_key(key)
        self._update_claude_status()
        messagebox.showinfo("Success", "Claude API key saved to keychain.")

    def _test_claude_connection(self) -> None:
        """Test Claude API connection."""
        key = get_claude_api_key()
        if not key:
            messagebox.showwarning(
                "Warning", "No API key configured. Please save an API key first."
            )
            return

        # Try to import and test
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=key)
            # Make a minimal API call
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'OK'"}],
            )
            messagebox.showinfo(
                "Success", "Connection successful! Claude API is working."
            )
        except anthropic.AuthenticationError:
            messagebox.showerror(
                "Error", "Authentication failed. Please check your API key."
            )
        except anthropic.RateLimitError:
            messagebox.showwarning("Warning", "Rate limited, but API key is valid.")
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")

    def _clear_claude_api_key(self) -> None:
        """Clear Claude API key from keychain."""
        if not has_claude_api_key():
            messagebox.showinfo("Info", "No API key to clear.")
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to remove the Claude API key?"):
            delete_claude_api_key()
            self._update_claude_status()
            messagebox.showinfo("Success", "Claude API key removed from keychain.")

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
        """Refresh settings data from config."""
        provider = get_provider()
        config = provider.config

        # Load current values into fields
        self.min_loss_usd.set(str(config.min_loss_usd))
        self.min_loss_pct.set(str(config.min_loss_pct))
        self.min_tax_benefit.set(str(config.min_tax_benefit))
        self.tax_rate.set(str(int(config.tax_rate * 100)))
        self.min_holding_days.set(str(config.min_holding_days))
        self.max_harvest_pct.set(str(config.max_harvest_pct))
        self.wash_window_days.set(str(config.wash_sale_days))
        self.paper_trading.set(config.alpaca_paper)

    def _on_save(self) -> None:
        """Save settings to config."""
        provider = get_provider()

        provider.update_config(
            min_loss_usd=Decimal(self.min_loss_usd.get()),
            min_loss_pct=Decimal(self.min_loss_pct.get()),
            min_tax_benefit=Decimal(self.min_tax_benefit.get()),
            tax_rate=Decimal(self.tax_rate.get()) / 100,
            min_holding_days=int(self.min_holding_days.get()),
            max_harvest_pct=Decimal(self.max_harvest_pct.get()),
            wash_sale_days=int(self.wash_window_days.get()),
            alpaca_paper=self.paper_trading.get(),
        )

    def _on_reset(self) -> None:
        """Reset settings to defaults."""
        self.min_loss_usd.set("100")
        self.min_loss_pct.set("3.0")
        self.min_tax_benefit.set("50")
        self.tax_rate.set("35")
        self.min_holding_days.set("7")
        self.max_harvest_pct.set("10.0")
        self.wash_window_days.set("30")
        self.paper_trading.set(True)
