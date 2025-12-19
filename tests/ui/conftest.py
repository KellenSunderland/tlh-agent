"""Pytest fixtures for UI testing."""

import contextlib
import os
import tkinter as tk
from pathlib import Path

import pytest

from tlh_agent.app import TLHAgentApp
from tlh_agent.ui.main_window import MainWindow

# Directory for screenshots
SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots"


@pytest.fixture(scope="module")
def screenshots_dir() -> Path:
    """Create and return the screenshots directory."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    return SCREENSHOTS_DIR


@pytest.fixture
def app(request):
    """Create a TLH Agent app instance for testing.

    The app is automatically destroyed after the test.
    """
    # Skip if no display available (CI environment)
    if os.environ.get("DISPLAY") is None and os.name != "nt":
        # Check if we're on macOS which doesn't need DISPLAY
        import platform

        if platform.system() != "Darwin":
            pytest.skip("No display available")

    app_instance = TLHAgentApp()

    yield app_instance

    # Cleanup
    with contextlib.suppress(tk.TclError):
        app_instance.root.destroy()


@pytest.fixture
def main_window(app) -> MainWindow:
    """Get the main window from the app."""
    return app.main_window


def take_screenshot(root: tk.Tk, filepath: Path) -> bool:
    """Take a screenshot of the tkinter window.

    Args:
        root: The root tkinter window.
        filepath: Path to save the screenshot.

    Returns:
        True if screenshot was taken successfully.
    """
    try:
        from PIL import ImageGrab

        # Update the window to ensure it's rendered
        root.update_idletasks()
        root.update()

        # Get window geometry
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        width = root.winfo_width()
        height = root.winfo_height()

        # Capture the screen region
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        screenshot.save(filepath)
        return True
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return False
