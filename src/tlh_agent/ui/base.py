"""Base classes for UI screens and components."""

import tkinter as tk
from tkinter import ttk
from typing import Protocol


class DataProvider(Protocol):
    """Protocol for data providers that screens can use."""

    def refresh(self) -> None:
        """Refresh data from source."""
        ...


class BaseScreen(ttk.Frame):
    """Base class for all application screens."""

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize the screen.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent, style="TFrame")
        self._setup_ui()
        self._bind_events()
        self.refresh()

    def _setup_ui(self) -> None:
        """Set up the screen UI. Override in subclasses."""
        pass

    def _bind_events(self) -> None:
        """Bind event handlers. Override in subclasses."""
        pass

    def refresh(self) -> None:
        """Refresh the screen data. Override in subclasses."""
        pass

    def on_show(self) -> None:
        """Called when screen becomes visible."""
        self.refresh()

    def on_hide(self) -> None:
        """Called when navigating away from this screen."""
        pass
