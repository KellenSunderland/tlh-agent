"""Helper utilities for UI testing."""

import contextlib
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WidgetInfo:
    """Information about a widget's position and properties."""

    widget: tk.Widget
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
    font: tuple | None = None
    fg: str | None = None
    bg: str | None = None


def get_widget_info(widget: tk.Widget) -> WidgetInfo:
    """Extract position and property information from a widget.

    Args:
        widget: The tkinter widget to inspect.

    Returns:
        WidgetInfo containing widget details.
    """
    # Ensure widget is rendered
    widget.update_idletasks()

    # Get geometry
    x = widget.winfo_x()
    y = widget.winfo_y()
    width = widget.winfo_width()
    height = widget.winfo_height()

    # Try to get common properties
    text = None
    font = None
    fg = None
    bg = None

    with contextlib.suppress(tk.TclError):
        text = widget.cget("text")

    with contextlib.suppress(tk.TclError):
        font = widget.cget("font")

    with contextlib.suppress(tk.TclError):
        fg = widget.cget("fg")
    if fg is None:
        with contextlib.suppress(tk.TclError):
            fg = widget.cget("foreground")

    with contextlib.suppress(tk.TclError):
        bg = widget.cget("bg")
    if bg is None:
        with contextlib.suppress(tk.TclError):
            bg = widget.cget("background")

    return WidgetInfo(
        widget=widget,
        x=x,
        y=y,
        width=width,
        height=height,
        text=text,
        font=font,
        fg=fg,
        bg=bg,
    )


def find_widgets_by_type(
    parent: tk.Widget, widget_type: type, recursive: bool = True
) -> list[tk.Widget]:
    """Find all widgets of a specific type.

    Args:
        parent: The parent widget to search in.
        widget_type: The type of widget to find.
        recursive: Whether to search recursively.

    Returns:
        List of matching widgets.
    """
    results = []

    for child in parent.winfo_children():
        if isinstance(child, widget_type):
            results.append(child)

        if recursive:
            results.extend(find_widgets_by_type(child, widget_type, recursive=True))

    return results


def find_widgets_with_text(
    parent: tk.Widget, text: str, partial: bool = False
) -> list[tk.Widget]:
    """Find widgets containing specific text.

    Args:
        parent: The parent widget to search in.
        text: The text to search for.
        partial: Whether to match partial text.

    Returns:
        List of matching widgets.
    """
    results = []

    for child in parent.winfo_children():
        try:
            widget_text = child.cget("text")
            is_partial_match = partial and text.lower() in str(widget_text).lower()
            is_exact_match = not partial and str(widget_text) == text
            if is_partial_match or is_exact_match:
                results.append(child)
        except tk.TclError:
            pass

        results.extend(find_widgets_with_text(child, text, partial))

    return results


def check_widget_visible(widget: tk.Widget) -> bool:
    """Check if a widget is visible on screen.

    Args:
        widget: The widget to check.

    Returns:
        True if the widget is visible.
    """
    widget.update_idletasks()
    return widget.winfo_viewable() and widget.winfo_width() > 0 and widget.winfo_height() > 0


def check_widgets_aligned_horizontally(
    widgets: list[tk.Widget], tolerance: int = 5
) -> bool:
    """Check if widgets are horizontally aligned (same y position).

    Args:
        widgets: List of widgets to check.
        tolerance: Allowed pixel difference.

    Returns:
        True if all widgets are aligned.
    """
    if len(widgets) < 2:
        return True

    for widget in widgets:
        widget.update_idletasks()

    base_y = widgets[0].winfo_rooty()
    return all(abs(w.winfo_rooty() - base_y) <= tolerance for w in widgets[1:])


def check_widgets_aligned_vertically(
    widgets: list[tk.Widget], tolerance: int = 5
) -> bool:
    """Check if widgets are vertically aligned (same x position).

    Args:
        widgets: List of widgets to check.
        tolerance: Allowed pixel difference.

    Returns:
        True if all widgets are aligned.
    """
    if len(widgets) < 2:
        return True

    for widget in widgets:
        widget.update_idletasks()

    base_x = widgets[0].winfo_rootx()
    return all(abs(w.winfo_rootx() - base_x) <= tolerance for w in widgets[1:])


def check_widget_contains_text(widget: tk.Widget, expected_texts: list[str]) -> dict[str, bool]:
    """Check if a widget or its children contain expected texts.

    Args:
        widget: The widget to check.
        expected_texts: List of texts that should be present.

    Returns:
        Dict mapping text to whether it was found.
    """
    results = dict.fromkeys(expected_texts, False)

    all_texts = collect_all_texts(widget)
    all_text_lower = [t.lower() for t in all_texts]

    for expected in expected_texts:
        if expected.lower() in all_text_lower or any(
            expected.lower() in t for t in all_text_lower
        ):
            results[expected] = True

    return results


def collect_all_texts(widget: tk.Widget) -> list[str]:
    """Collect all text content from a widget and its children.

    Args:
        widget: The widget to collect text from.

    Returns:
        List of all text strings found.
    """
    texts = []

    try:
        text = widget.cget("text")
        if text:
            texts.append(str(text))
    except tk.TclError:
        pass

    for child in widget.winfo_children():
        texts.extend(collect_all_texts(child))

    return texts


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


def validate_color_format(color: str | None) -> bool:
    """Validate that a color string is in proper format.

    Args:
        color: The color string to validate.

    Returns:
        True if color format is valid.
    """
    if color is None:
        return False

    # Check hex format
    if color.startswith("#"):
        return len(color) in (4, 7, 9) and all(
            c in "0123456789abcdefABCDEF" for c in color[1:]
        )

    # Named colors are also valid
    return True


def get_widget_hierarchy(widget: tk.Widget, depth: int = 0) -> str:
    """Get a string representation of the widget hierarchy.

    Args:
        widget: The root widget.
        depth: Current depth for indentation.

    Returns:
        String showing widget hierarchy.
    """
    indent = "  " * depth
    widget_class = widget.__class__.__name__

    try:
        text = widget.cget("text")
        text_info = f' text="{text}"' if text else ""
    except tk.TclError:
        text_info = ""

    result = f"{indent}{widget_class}{text_info}\n"

    for child in widget.winfo_children():
        result += get_widget_hierarchy(child, depth + 1)

    return result
