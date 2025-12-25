"""Main application orchestrator for TLH Agent."""

import tkinter as tk

from tlh_agent.services import ServiceProvider, set_provider
from tlh_agent.ui.main_window import MainWindow
from tlh_agent.ui.theme import Theme


class TLHAgentApp:
    """Main application class that orchestrates the TLH Agent."""

    def __init__(self) -> None:
        """Initialize the application."""
        self.root = tk.Tk()
        self.root.title("TLH Agent")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        # Initialize services
        self.services = ServiceProvider.create()
        set_provider(self.services)

        # Configure theme
        Theme.configure_styles(self.root)
        self.root.configure(bg=Theme.colors.BG_PRIMARY)

        # Create main window
        self.main_window = MainWindow(self.root)
        self.main_window.pack(fill=tk.BOTH, expand=True)

    def run(self) -> None:
        """Start the application main loop."""
        self.root.mainloop()
