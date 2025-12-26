"""Trade queue screen for managing pending trade recommendations.

Displays trades from multiple sources:
- Harvest opportunities (tax-loss harvesting sells)
- Index buys (S&P 500 tracking purchases)
- Rebalance trades (drift correction)
"""

import tkinter as tk
from collections.abc import Callable
from decimal import Decimal
from tkinter import messagebox, ttk
from typing import Any

from tlh_agent.data.mock_data import HarvestOpportunity, MockDataFactory
from tlh_agent.services import get_provider
from tlh_agent.services.execution import ExecutionStatus
from tlh_agent.services.scanner import HarvestOpportunity as LiveHarvestOpportunity
from tlh_agent.services.trade_queue import TradeQueueService, TradeStatus
from tlh_agent.ui.base import BaseScreen
from tlh_agent.ui.components.card import Card
from tlh_agent.ui.components.data_table import ColumnDef, DataTable
from tlh_agent.ui.components.page_header import PageHeader
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class TradeQueueScreen(BaseScreen):
    """Screen for reviewing and acting on pending trades from all sources."""

    def __init__(
        self,
        parent: tk.Widget,
        trade_queue: TradeQueueService | None = None,
        on_navigate_to_dashboard: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the screen.

        Args:
            parent: The parent widget.
            trade_queue: Trade queue service for assistant-added trades.
            on_navigate_to_dashboard: Callback to navigate to dashboard and refresh.
        """
        self._trade_queue = trade_queue
        self._on_navigate_to_dashboard = on_navigate_to_dashboard
        self._all_table_data: list[dict] = []  # Unfiltered data
        self._last_trade_count = 0  # Track trade count for auto-refresh
        self._refresh_job: str | None = None
        self._progress_window: tk.Toplevel | None = None
        super().__init__(parent)
        self._schedule_auto_refresh()

    def _setup_ui(self) -> None:
        """Set up the trade queue layout."""
        # Header
        header = PageHeader(self, title="Trade Queue", subtitle="Review and execute pending trades")
        header.pack(fill=tk.X, pady=(0, Spacing.LG))

        # Total savings display in header actions
        self.total_savings_label = tk.Label(
            header.actions,
            text="Potential Savings: $0.00",
            font=Fonts.BODY_BOLD,
            fg=Colors.SUCCESS_TEXT,
            bg=Colors.BG_PRIMARY,
        )
        self.total_savings_label.pack(side=tk.RIGHT)

        # Summary card
        summary_card = Card(self, title="Queue Summary")
        summary_card.pack(fill=tk.X, pady=(0, Spacing.MD))

        summary_content = summary_card.content
        self.summary_labels: dict[str, tk.Label] = {}
        for key, label in [
            ("total", "Total Trades"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("total_loss", "Total Loss"),
            ("tax_benefit", "Tax Benefit"),
        ]:
            frame = tk.Frame(summary_content, bg=Colors.BG_SECONDARY)
            frame.pack(side=tk.LEFT, padx=(0, Spacing.XL))

            tk.Label(
                frame,
                text=label,
                font=Fonts.CAPTION,
                fg=Colors.TEXT_MUTED,
                bg=Colors.BG_SECONDARY,
            ).pack(anchor=tk.W)

            value_label = tk.Label(
                frame,
                text="0",
                font=Fonts.BODY_BOLD,
                fg=Colors.TEXT_PRIMARY,
                bg=Colors.BG_SECONDARY,
            )
            value_label.pack(anchor=tk.W)
            self.summary_labels[key] = value_label

        # Filter row
        filter_frame = tk.Frame(self, bg=Colors.BG_PRIMARY)
        filter_frame.pack(fill=tk.X, pady=(0, Spacing.SM))

        tk.Label(
            filter_frame,
            text="Filter:",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._apply_filter())
        self._filter_entry = tk.Entry(
            filter_frame,
            textvariable=self._filter_var,
            font=Fonts.BODY,
            bg=Colors.BG_SECONDARY,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.TEXT_PRIMARY,
            relief=tk.FLAT,
            width=20,
        )
        self._filter_entry.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        tk.Label(
            filter_frame,
            text="(search by ticker or name)",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY,
        ).pack(side=tk.LEFT)

        # Trade queue table in card
        table_card = Card(self, title="Pending Trades")
        table_card.pack(fill=tk.BOTH, expand=True, pady=(0, Spacing.MD))

        columns = [
            ColumnDef("trade_type", "Type", width=80),
            ColumnDef("status", "Status", width=70),
            ColumnDef("ticker", "Ticker", width=70),
            ColumnDef("name", "Name", width=150),
            ColumnDef("action", "Action", width=60),
            ColumnDef("shares", "Shares", width=70, anchor="e"),
            ColumnDef("amount", "Amount", width=90, anchor="e"),
            ColumnDef("tax_benefit", "Tax Benefit", width=90, anchor="e"),
        ]

        self.table = DataTable(
            table_card.content,
            columns=columns,
            on_select=self._on_select,
        )
        self.table.pack(fill=tk.BOTH, expand=True)

        # Action buttons row
        action_frame = ttk.Frame(self, style="TFrame")
        action_frame.pack(fill=tk.X, pady=(0, Spacing.MD))

        # Selected item actions
        self.approve_btn = tk.Button(
            action_frame,
            text="Approve Selected",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.SUCCESS,
            activebackground="#28a745",
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_approve,
        )
        self.approve_btn.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        self.reject_btn = tk.Button(
            action_frame,
            text="Reject Selected",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.DANGER,
            activebackground="#c82333",
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_reject,
        )
        self.reject_btn.pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Bulk actions
        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=Spacing.MD
        )

        tk.Button(
            action_frame,
            text="Approve All",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BORDER,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_approve_all,
        ).pack(side=tk.LEFT, padx=(0, Spacing.SM))

        tk.Button(
            action_frame,
            text="Reject All",
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BORDER,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_reject_all,
        ).pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Execute button (right aligned)
        tk.Button(
            action_frame,
            text="Execute Approved",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.ACCENT,
            activebackground=Colors.ACCENT_HOVER,
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.LG,
            pady=Spacing.SM,
            cursor="hand2",
            command=self._on_execute,
        ).pack(side=tk.RIGHT)

        # Details panel in card
        details_card = Card(self, title="Details")
        details_card.pack(fill=tk.X)

        self.details_frame = details_card.content

        self.details_label = tk.Label(
            self.details_frame,
            text="Select a trade to view details",
            font=Fonts.BODY,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
            anchor=tk.W,
        )
        self.details_label.pack(fill=tk.X)

    def refresh(self) -> None:
        """Refresh harvest queue data."""
        provider = get_provider()
        table_data = []

        # Get harvest opportunities from scanner
        if provider.is_live and provider.scanner:
            scan_result = provider.scanner.scan()
            opportunities = scan_result.opportunities
        else:
            opportunities = MockDataFactory.get_harvest_opportunities()

        # Add harvest opportunities to table
        for opp in opportunities:
            status_display = opp.status.title()
            tag = ""
            if opp.status == "approved":
                tag = "gain"
            elif opp.status in ("rejected", "expired"):
                tag = "muted"

            amount = opp.shares * opp.current_price

            table_data.append(
                {
                    "trade_type": "Harvest",
                    "status": status_display,
                    "ticker": opp.ticker,
                    "name": opp.name,
                    "action": "Sell",
                    "shares": f"{opp.shares:,.2f}",
                    "amount": f"${amount:,.2f}",
                    "tax_benefit": f"${opp.estimated_tax_benefit:,.2f}",
                    "tag": tag,
                    "_opportunity": opp,
                }
            )

        # Get trades from trade queue service (added by assistant)
        if self._trade_queue:
            queued_trades = self._trade_queue.get_pending_trades()
            for trade in queued_trades:
                type_display = trade.trade_type.value.replace("_", " ").title()
                status_display = trade.status.value.title()
                tag = ""
                if trade.status.value == "approved":
                    tag = "gain"

                table_data.append(
                    {
                        "trade_type": type_display,
                        "status": status_display,
                        "ticker": trade.symbol,
                        "name": trade.name,
                        "action": trade.action.value.title(),
                        "shares": f"{trade.shares:,.2f}",
                        "amount": f"${trade.notional:,.2f}",
                        "tax_benefit": "-",
                        "tag": tag,
                        "_queued_trade": trade,
                    }
                )

        # Update summary counts
        total_count = len(table_data)
        pending_count = sum(1 for o in opportunities if o.status == "pending")
        approved_count = sum(1 for o in opportunities if o.status == "approved")
        if self._trade_queue:
            pending_count += len(self._trade_queue.get_pending_trades())
        active_statuses = ("pending", "approved")
        total_loss = sum(o.unrealized_loss for o in opportunities if o.status in active_statuses)
        total_benefit = sum(
            o.estimated_tax_benefit for o in opportunities if o.status in active_statuses
        )

        self.summary_labels["total"].configure(text=str(total_count))
        self.summary_labels["pending"].configure(text=str(pending_count))
        self.summary_labels["approved"].configure(text=str(approved_count))
        self.summary_labels["total_loss"].configure(
            text=f"${total_loss:,.2f}",
            fg=Colors.DANGER_TEXT,
        )
        self.summary_labels["tax_benefit"].configure(
            text=f"${total_benefit:,.2f}",
            fg=Colors.SUCCESS_TEXT,
        )

        # Update total savings
        self.total_savings_label.configure(text=f"Potential Savings: ${total_benefit:,.2f}")

        # Store unfiltered data and apply any active filter
        self._all_table_data = table_data
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply the current filter to table data."""
        filter_text = self._filter_var.get().strip().lower()

        if not filter_text:
            # No filter, show all data
            self.table.set_data(self._all_table_data)
            return

        # Filter by ticker or name
        filtered = [
            row for row in self._all_table_data
            if filter_text in row.get("ticker", "").lower()
            or filter_text in row.get("name", "").lower()
        ]
        self.table.set_data(filtered)

    def _schedule_auto_refresh(self) -> None:
        """Schedule periodic check for new trades."""
        self._check_for_updates()
        # Check every 2 seconds
        self._refresh_job = self.after(2000, self._schedule_auto_refresh)

    def destroy(self) -> None:
        """Clean up when widget is destroyed."""
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        super().destroy()

    def _check_for_updates(self) -> None:
        """Check if trade count changed and refresh if needed."""
        if not self._trade_queue:
            return

        current_count = len(self._trade_queue.get_all_trades())
        if current_count != self._last_trade_count:
            self._last_trade_count = current_count
            self.refresh()

    def _on_select(self, row: dict[str, Any]) -> None:
        """Handle row selection."""
        opp = row.get("_opportunity")
        if not isinstance(opp, (HarvestOpportunity, LiveHarvestOpportunity)):
            return

        self._show_details(opp)

    def _show_details(self, opp: HarvestOpportunity) -> None:
        """Show details for a harvest opportunity."""
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        # Details grid
        details = tk.Frame(self.details_frame, bg=Colors.BG_SECONDARY)
        details.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        # Row 1: Ticker info
        row1 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row1.pack(fill=tk.X, pady=2)

        tk.Label(
            row1,
            text=f"{opp.ticker} - {opp.name}",
            font=Fonts.BODY_BOLD,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT)

        tk.Label(
            row1,
            text=f"Status: {opp.status.title()}",
            font=Fonts.BODY,
            fg=Colors.ACCENT if opp.status == "approved" else Colors.TEXT_MUTED,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.RIGHT)

        # Row 2: Financial details
        row2 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row2.pack(fill=tk.X, pady=2)

        for label, value, color in [
            ("Shares:", f"{opp.shares:,.2f}", Colors.TEXT_PRIMARY),
            ("Current Price:", f"${opp.current_price:,.2f}", Colors.TEXT_PRIMARY),
            ("Cost Basis:", f"${opp.cost_basis:,.2f}", Colors.TEXT_PRIMARY),
            ("Unrealized Loss:", f"${opp.unrealized_loss:,.2f}", Colors.DANGER_TEXT),
            ("Est. Tax Benefit:", f"${opp.estimated_tax_benefit:,.2f}", Colors.SUCCESS_TEXT),
        ]:
            tk.Label(
                row2,
                text=f"{label} {value}",
                font=Fonts.BODY,
                fg=color,
                bg=Colors.BG_SECONDARY,
            ).pack(side=tk.LEFT, padx=(0, Spacing.LG))

        # Row 3: Action recommendation
        row3 = tk.Frame(details, bg=Colors.BG_SECONDARY)
        row3.pack(fill=tk.X, pady=2)

        action_text = f"Recommended: {opp.recommended_action.title()}"
        if opp.swap_target:
            action_text += f" to {opp.swap_target}"

        tk.Label(
            row3,
            text=action_text,
            font=Fonts.BODY,
            fg=Colors.ACCENT,
            bg=Colors.BG_SECONDARY,
        ).pack(side=tk.LEFT)

    def _on_approve(self) -> None:
        """Approve selected trade (harvest opportunity or queued trade)."""
        selected = self.table.get_selected()
        if not selected:
            return

        # Handle harvest opportunities
        opp = selected.get("_opportunity")
        if opp and hasattr(opp, "id"):
            provider = get_provider()
            if provider.scanner:
                provider.scanner.approve_harvest(opp.id)
                self.refresh()
                return

        # Handle queued trades
        queued = selected.get("_queued_trade")
        if queued and self._trade_queue:
            self._trade_queue.approve_trade(queued.id)
            self.refresh()

    def _on_reject(self) -> None:
        """Reject/remove selected trade."""
        selected = self.table.get_selected()
        if not selected:
            return

        # Handle harvest opportunities
        opp = selected.get("_opportunity")
        if opp and hasattr(opp, "id"):
            provider = get_provider()
            if provider.scanner:
                provider.scanner.reject_harvest(opp.id)
                self.refresh()
                return

        # Handle queued trades - remove from queue
        queued = selected.get("_queued_trade")
        if queued and self._trade_queue:
            self._trade_queue.remove_trade(queued.id)
            self.refresh()

    def _on_approve_all(self) -> None:
        """Approve all pending trades."""
        provider = get_provider()

        # Approve harvest opportunities
        if provider.scanner:
            scan_result = provider.scanner.scan()
            for opp in scan_result.opportunities:
                if opp.status == "pending":
                    provider.scanner.approve_harvest(opp.id)

        # Approve queued trades
        if self._trade_queue:
            self._trade_queue.approve_all()

        self.refresh()

    def _on_reject_all(self) -> None:
        """Reject/clear all pending trades."""
        provider = get_provider()

        # Reject harvest opportunities
        if provider.scanner:
            scan_result = provider.scanner.scan()
            for opp in scan_result.opportunities:
                if opp.status == "pending":
                    provider.scanner.reject_harvest(opp.id)

        # Clear all queued trades
        if self._trade_queue:
            self._trade_queue.clear_queue()

        self.refresh()

    def _on_execute(self) -> None:
        """Execute all approved trades with progress feedback."""
        provider = get_provider()

        if not provider.execution:
            messagebox.showerror(
                "Error", "Execution service not available. Check Alpaca connection."
            )
            return

        # Collect all approved trades
        approved_harvests = []
        if provider.scanner:
            scan_result = provider.scanner.scan()
            approved_harvests = [o for o in scan_result.opportunities if o.status == "approved"]

        approved_queued = []
        if self._trade_queue:
            approved_queued = self._trade_queue.get_trades_by_status(TradeStatus.APPROVED)

        total_trades = len(approved_harvests) + len(approved_queued)

        if total_trades == 0:
            messagebox.showinfo("No Trades", "No approved trades to execute. Approve trades first.")
            return

        # Show progress window
        self._show_progress_window(total_trades)

        # Track results
        results = {
            "success": 0,
            "failed": 0,
            "pending": 0,
            "total_value": Decimal("0"),
            "errors": [],
        }

        current = 0

        # Execute harvest opportunities
        for opp in approved_harvests:
            current += 1
            self._update_progress(current, total_trades, opp.ticker, "Selling")

            result = provider.execution.execute_harvest(opp)

            if result.status == ExecutionStatus.SUCCESS:
                results["success"] += 1
                results["total_value"] += result.total_value
            elif result.status == ExecutionStatus.PENDING:
                results["pending"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{opp.ticker}: {result.error_message}")

        # Execute queued trades
        for trade in approved_queued:
            current += 1
            action = "Buying" if trade.action.value == "buy" else "Selling"
            self._update_progress(current, total_trades, trade.symbol, action)

            result = provider.execution.execute_queued_trade(trade)

            if result.status == ExecutionStatus.SUCCESS:
                self._trade_queue.mark_executed(trade.id, result.price)
                results["success"] += 1
                results["total_value"] += result.total_value
            elif result.status == ExecutionStatus.PENDING:
                results["pending"] += 1
            else:
                self._trade_queue.mark_failed(trade.id, result.error_message or "Unknown error")
                results["failed"] += 1
                results["errors"].append(f"{trade.symbol}: {result.error_message}")

        # Close progress window
        self._close_progress_window()

        # Show summary
        self._show_execution_summary(results)

        # Refresh this screen
        self.refresh()

    def _show_progress_window(self, total: int) -> None:
        """Show execution progress window."""
        self._progress_window = tk.Toplevel(self)
        self._progress_window.title("Executing Trades")
        self._progress_window.geometry("400x200")
        self._progress_window.resizable(False, False)
        self._progress_window.transient(self.winfo_toplevel())
        self._progress_window.grab_set()

        # Center on parent
        self._progress_window.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 400) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 200) // 2
        self._progress_window.geometry(f"+{x}+{y}")

        frame = tk.Frame(self._progress_window, bg=Colors.BG_PRIMARY, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        self._progress_title = tk.Label(
            frame,
            text="Executing Trades...",
            font=Fonts.HEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_PRIMARY,
        )
        self._progress_title.pack(pady=(0, 15))

        self._progress_label = tk.Label(
            frame,
            text=f"0 / {total}",
            font=Fonts.BODY_BOLD,
            fg=Colors.ACCENT,
            bg=Colors.BG_PRIMARY,
        )
        self._progress_label.pack(pady=(0, 10))

        self._progress_bar = ttk.Progressbar(
            frame,
            length=350,
            mode="determinate",
            maximum=total,
        )
        self._progress_bar.pack(pady=(0, 10))

        self._progress_current = tk.Label(
            frame,
            text="Preparing...",
            font=Fonts.BODY,
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_PRIMARY,
        )
        self._progress_current.pack()

        self._progress_stats = tk.Label(
            frame,
            text="Success: 0  |  Failed: 0",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_PRIMARY,
        )
        self._progress_stats.pack(pady=(10, 0))

        self._progress_window.update()

    def _update_progress(self, current: int, total: int, symbol: str, action: str) -> None:
        """Update progress window."""
        if not self._progress_window:
            return

        self._progress_label.configure(text=f"{current} / {total}")
        self._progress_bar["value"] = current
        self._progress_current.configure(text=f"{action} {symbol}...")
        self._progress_window.update()

    def _close_progress_window(self) -> None:
        """Close progress window."""
        if self._progress_window:
            self._progress_window.destroy()
            self._progress_window = None

    def _show_execution_summary(self, results: dict) -> None:
        """Show execution summary dialog."""
        success = results["success"]
        failed = results["failed"]
        pending = results["pending"]
        total_value = results["total_value"]
        errors = results["errors"]

        # Build message
        if success > 0 and failed == 0:
            title = "Execution Complete"
            icon = "info"
            msg = f"{success} trade(s) executed successfully!\n\n"
            msg += f"Total value: ${total_value:,.2f}"
        elif failed > 0 and success > 0:
            title = "Execution Partially Complete"
            icon = "warning"
            msg = f"{success} succeeded, {failed} failed\n\n"
            msg += f"Total value: ${total_value:,.2f}\n\n"
            msg += "Errors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more"
        elif failed > 0:
            title = "Execution Failed"
            icon = "error"
            msg = f"All {failed} trade(s) failed.\n\n"
            msg += "Errors:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more"
        else:
            title = "No Trades Executed"
            icon = "info"
            msg = "No trades were executed."

        if pending > 0:
            msg += f"\n\n{pending} order(s) are pending fill."

        # Show dialog with option to view positions
        if success > 0:
            result = messagebox.askyesno(
                title,
                msg + "\n\nView updated positions on Dashboard?",
                icon=icon,
            )
            if result and self._on_navigate_to_dashboard:
                self._on_navigate_to_dashboard()
        else:
            if icon == "error":
                messagebox.showerror(title, msg)
            elif icon == "warning":
                messagebox.showwarning(title, msg)
            else:
                messagebox.showinfo(title, msg)
