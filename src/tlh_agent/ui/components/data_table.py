"""Reusable data table component with sorting and selection."""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Literal

from tlh_agent.ui.theme import Colors

# Valid anchor values for treeview
AnchorType = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]


@dataclass
class ColumnDef:
    """Definition of a table column."""

    key: str
    header: str
    width: int = 100
    anchor: AnchorType = "w"
    sortable: bool = True
    formatter: Callable[[Any], str] | None = None


class DataTable(ttk.Frame):
    """Sortable, selectable data table component."""

    def __init__(
        self,
        parent: tk.Widget,
        columns: list[ColumnDef],
        on_select: Callable[[dict[str, Any]], None] | None = None,
        on_double_click: Callable[[dict[str, Any]], None] | None = None,
        show_header: bool = True,
    ) -> None:
        """Initialize the data table.

        Args:
            parent: The parent widget.
            columns: List of column definitions.
            on_select: Callback when a row is selected.
            on_double_click: Callback when a row is double-clicked.
            show_header: Whether to show the header row.
        """
        super().__init__(parent, style="TFrame")

        self._columns = columns
        self._on_select = on_select
        self._on_double_click = on_double_click
        self._data: list[dict[str, Any]] = []
        self._sort_column: str | None = None
        self._sort_ascending: bool = True

        self._setup_ui(show_header)

    def _setup_ui(self, show_header: bool) -> None:
        """Set up the table UI."""
        # Create treeview with columns
        column_ids = [col.key for col in self._columns]
        show_option = "headings" if show_header else ""

        self._tree = ttk.Treeview(
            self,
            columns=column_ids,
            show=show_option,
            selectmode="browse",
            style="Treeview",
        )

        # Configure columns
        for col in self._columns:
            sortable = col.sortable
            self._tree.heading(
                col.key,
                text=col.header,
                anchor=col.anchor,
                command=lambda c=col.key, s=sortable: self._on_header_click(c) if s else None,
            )
            self._tree.column(
                col.key,
                width=col.width,
                minwidth=50,
                anchor=col.anchor,
            )

        # Scrollbars
        v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._tree.yview)
        h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Grid layout
        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Bind events
        self._tree.bind("<<TreeviewSelect>>", self._handle_select)
        self._tree.bind("<Double-1>", self._handle_double_click)
        self._tree.bind("<Motion>", self._handle_motion)
        self._tree.bind("<Leave>", self._handle_leave)

        # Track hovered row
        self._hovered_item: str | None = None

        # Custom row styling
        self._tree.tag_configure("gain", foreground=Colors.SUCCESS_TEXT)
        self._tree.tag_configure("loss", foreground=Colors.DANGER_TEXT)
        self._tree.tag_configure("muted", foreground=Colors.TEXT_MUTED)
        self._tree.tag_configure("accent", foreground=Colors.ACCENT)
        self._tree.tag_configure("striped", background=Colors.BG_TERTIARY)
        self._tree.tag_configure("hover", background=Colors.BG_SECONDARY)

    def set_data(self, data: list[dict[str, Any]]) -> None:
        """Set the table data.

        Args:
            data: List of row data dictionaries.
        """
        self._data = data
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the displayed data."""
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Sort if needed
        display_data = self._data.copy()
        if self._sort_column:
            display_data.sort(
                key=lambda row: row.get(self._sort_column, ""),
                reverse=not self._sort_ascending,
            )

        # Insert rows
        for i, row in enumerate(display_data):
            values = []
            for col in self._columns:
                value = row.get(col.key, "")
                if col.formatter:
                    value = col.formatter(value)
                values.append(value)

            # Determine row tag
            tags: tuple[str, ...] = ()
            if "tag" in row:
                tags = (row["tag"],)
            elif i % 2 == 1:
                tags = ("striped",)

            # Store original row data in item
            item_id = self._tree.insert("", tk.END, values=values, tags=tags)
            self._tree.set(item_id, self._columns[0].key, values[0])

        # Update header sort indicators
        self._update_sort_indicators()

    def _update_sort_indicators(self) -> None:
        """Update column header sort indicators."""
        for col in self._columns:
            indicator = ""
            if col.key == self._sort_column:
                indicator = " ▲" if self._sort_ascending else " ▼"
            self._tree.heading(col.key, text=f"{col.header}{indicator}")

    def _on_header_click(self, column: str) -> None:
        """Handle column header click for sorting.

        Args:
            column: The column key that was clicked.
        """
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        self._refresh_display()

    def _handle_select(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Handle row selection event."""
        if not self._on_select:
            return

        selection = self._tree.selection()
        if selection:
            item = selection[0]
            index = self._tree.index(item)
            if 0 <= index < len(self._data):
                self._on_select(self._data[index])

    def _handle_double_click(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Handle row double-click event."""
        if not self._on_double_click:
            return

        selection = self._tree.selection()
        if selection:
            item = selection[0]
            index = self._tree.index(item)
            if 0 <= index < len(self._data):
                self._on_double_click(self._data[index])

    def _handle_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Handle mouse motion for hover effect."""
        item = self._tree.identify_row(event.y)

        if item != self._hovered_item:
            # Remove hover from previous item
            if self._hovered_item:
                tags = list(self._tree.item(self._hovered_item, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self._tree.item(self._hovered_item, tags=tags)

            # Add hover to new item
            if item:
                tags = list(self._tree.item(item, "tags"))
                if "hover" not in tags:
                    tags.append("hover")
                    self._tree.item(item, tags=tags)

            self._hovered_item = item

    def _handle_leave(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Handle mouse leaving the table."""
        if self._hovered_item:
            tags = list(self._tree.item(self._hovered_item, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                self._tree.item(self._hovered_item, tags=tags)
            self._hovered_item = None

    def get_selected(self) -> dict[str, Any] | None:
        """Get the currently selected row data.

        Returns:
            The selected row data, or None if nothing is selected.
        """
        selection = self._tree.selection()
        if selection:
            item = selection[0]
            index = self._tree.index(item)
            if 0 <= index < len(self._data):
                return self._data[index]
        return None

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self._tree.selection_remove(self._tree.selection())

    def sort_by(self, column: str, ascending: bool = True) -> None:
        """Sort the table by a specific column.

        Args:
            column: The column key to sort by.
            ascending: Whether to sort ascending.
        """
        self._sort_column = column
        self._sort_ascending = ascending
        self._refresh_display()
