"""Theme configuration for TLH Agent - AWS Dark palette with Inter font."""

import contextlib
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk
from typing import ClassVar


def _get_available_font(preferences: list[str], fallback: str = "TkDefaultFont") -> str:
    """Get the first available font from a list of preferences.

    Args:
        preferences: List of font names in order of preference.
        fallback: Fallback font if none are available.

    Returns:
        The first available font name.
    """
    try:
        # Need a temporary root to query fonts
        temp_root = tk._default_root
        if temp_root is None:
            return preferences[0]  # Can't check, assume first is available

        available = tkfont.families(temp_root)
        available_lower = [f.lower() for f in available]

        for pref in preferences:
            if pref.lower() in available_lower:
                # Return the actual name from the system
                idx = available_lower.index(pref.lower())
                return available[idx]

        return fallback
    except Exception:
        return preferences[0]


@dataclass(frozen=True)
class Colors:
    """AWS Dark color palette."""

    # Backgrounds
    BG_PRIMARY: ClassVar[str] = "#1a242f"  # Deep navy (main background)
    BG_SECONDARY: ClassVar[str] = "#232f3e"  # AWS navy (cards, sidebar)
    BG_TERTIARY: ClassVar[str] = "#2a3f54"  # Lighter navy (hover states)
    BG_INPUT: ClassVar[str] = "#2a3f54"  # Input field background (slightly lighter)

    # Text
    TEXT_PRIMARY: ClassVar[str] = "#ffffff"  # White
    TEXT_SECONDARY: ClassVar[str] = "#d5dbdb"  # Light gray
    TEXT_MUTED: ClassVar[str] = "#879596"  # Muted gray

    # Accent colors
    ACCENT: ClassVar[str] = "#ff9900"  # AWS Orange (primary actions)
    ACCENT_HOVER: ClassVar[str] = "#ec7211"  # Darker orange
    SUCCESS: ClassVar[str] = "#1d8102"  # Green (gains)
    SUCCESS_TEXT: ClassVar[str] = "#7dcea0"  # Light green text
    DANGER: ClassVar[str] = "#d13212"  # Red (losses)
    DANGER_TEXT: ClassVar[str] = "#f1948a"  # Light red text
    WARNING: ClassVar[str] = "#ff9900"  # Orange (alerts)
    INFO: ClassVar[str] = "#00a1c9"  # AWS Teal (info states)

    # Borders and dividers
    BORDER: ClassVar[str] = "#3b4a5a"  # Subtle borders
    BORDER_LIGHT: ClassVar[str] = "#4a5a6a"  # Lighter border for focus


# Font preferences in order (Inter -> SF Pro -> Helvetica Neue -> system)
_FONT_PREFERENCES = ["Inter", "SF Pro Text", "SF Pro", "Helvetica Neue", "Helvetica"]
_MONO_PREFERENCES = ["JetBrains Mono", "SF Mono", "Menlo", "Monaco", "Courier New"]


class Fonts:
    """Typography using Inter font family with macOS fallbacks."""

    # These will be set on first access after tk is initialized
    _family: ClassVar[str | None] = None
    _family_mono: ClassVar[str | None] = None

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Initialize font families if not already done."""
        if cls._family is None:
            cls._family = _get_available_font(_FONT_PREFERENCES, "TkDefaultFont")
        if cls._family_mono is None:
            cls._family_mono = _get_available_font(_MONO_PREFERENCES, "TkFixedFont")

    @classmethod
    @property
    def FAMILY(cls) -> str:
        """Primary font family."""
        cls._ensure_initialized()
        return cls._family  # type: ignore[return-value]

    @classmethod
    @property
    def FAMILY_MONO(cls) -> str:
        """Monospace font family."""
        cls._ensure_initialized()
        return cls._family_mono  # type: ignore[return-value]

    @classmethod
    @property
    def HEADING(cls) -> tuple[str, int, str]:
        """Heading font tuple."""
        cls._ensure_initialized()
        return (cls._family, 20, "bold")  # type: ignore[return-value]

    @classmethod
    @property
    def SUBHEADING(cls) -> tuple[str, int, str]:
        """Subheading font tuple."""
        cls._ensure_initialized()
        return (cls._family, 16, "bold")  # type: ignore[return-value]

    @classmethod
    @property
    def BODY(cls) -> tuple[str, int]:
        """Body font tuple."""
        cls._ensure_initialized()
        return (cls._family, 13)  # type: ignore[return-value]

    @classmethod
    @property
    def BODY_BOLD(cls) -> tuple[str, int, str]:
        """Bold body font tuple."""
        cls._ensure_initialized()
        return (cls._family, 13, "bold")  # type: ignore[return-value]

    @classmethod
    @property
    def CAPTION(cls) -> tuple[str, int]:
        """Caption font tuple."""
        cls._ensure_initialized()
        return (cls._family, 11)  # type: ignore[return-value]

    @classmethod
    @property
    def MONO(cls) -> tuple[str, int]:
        """Monospace font tuple."""
        cls._ensure_initialized()
        return (cls._family_mono, 12)  # type: ignore[return-value]

    @classmethod
    @property
    def MONO_SMALL(cls) -> tuple[str, int]:
        """Small monospace font tuple."""
        cls._ensure_initialized()
        return (cls._family_mono, 10)  # type: ignore[return-value]


@dataclass(frozen=True)
class Spacing:
    """Consistent spacing values."""

    XS: ClassVar[int] = 4
    SM: ClassVar[int] = 8
    MD: ClassVar[int] = 16
    LG: ClassVar[int] = 24
    XL: ClassVar[int] = 32


@dataclass(frozen=True)
class Sizes:
    """Component sizes."""

    SIDEBAR_WIDTH: ClassVar[int] = 200
    CARD_MIN_WIDTH: ClassVar[int] = 180
    CARD_HEIGHT: ClassVar[int] = 100
    TABLE_ROW_HEIGHT: ClassVar[int] = 36
    BUTTON_HEIGHT: ClassVar[int] = 32
    INPUT_HEIGHT: ClassVar[int] = 32
    NAV_ITEM_HEIGHT: ClassVar[int] = 44


class Theme:
    """Central theme configuration and style application."""

    colors = Colors
    fonts = Fonts
    spacing = Spacing
    sizes = Sizes

    @classmethod
    def configure_styles(cls, root) -> None:
        """Configure ttk styles for the application."""
        style = ttk.Style(root)

        # Use clam theme for better dark theme customization
        # (aqua theme on macOS overrides many custom styles)
        style.theme_use("clam")

        # Configure base styles
        style.configure(
            ".",
            background=Colors.BG_PRIMARY,
            foreground=Colors.TEXT_PRIMARY,
            font=Fonts.BODY,
        )

        # Frame styles
        style.configure("TFrame", background=Colors.BG_PRIMARY)
        style.configure("Card.TFrame", background=Colors.BG_SECONDARY)
        style.configure("Sidebar.TFrame", background=Colors.BG_SECONDARY)

        # Label styles
        style.configure(
            "TLabel",
            background=Colors.BG_PRIMARY,
            foreground=Colors.TEXT_PRIMARY,
            font=Fonts.BODY,
        )
        style.configure(
            "Heading.TLabel",
            font=Fonts.HEADING,
            foreground=Colors.TEXT_PRIMARY,
        )
        style.configure(
            "Subheading.TLabel",
            font=Fonts.SUBHEADING,
            foreground=Colors.TEXT_PRIMARY,
        )
        style.configure(
            "Caption.TLabel",
            font=Fonts.CAPTION,
            foreground=Colors.TEXT_MUTED,
        )
        style.configure(
            "Card.TLabel",
            background=Colors.BG_SECONDARY,
            foreground=Colors.TEXT_PRIMARY,
        )
        style.configure(
            "Success.TLabel",
            foreground=Colors.SUCCESS_TEXT,
        )
        style.configure(
            "Danger.TLabel",
            foreground=Colors.DANGER_TEXT,
        )
        style.configure(
            "Accent.TLabel",
            foreground=Colors.ACCENT,
        )
        style.configure(
            "Muted.TLabel",
            foreground=Colors.TEXT_MUTED,
        )

        # Button styles
        style.configure(
            "TButton",
            background=Colors.BG_TERTIARY,
            foreground=Colors.TEXT_PRIMARY,
            font=Fonts.BODY_BOLD,
            padding=(Spacing.MD, Spacing.SM),
        )
        style.map(
            "TButton",
            background=[("active", Colors.BORDER_LIGHT), ("pressed", Colors.BORDER)],
        )

        style.configure(
            "Accent.TButton",
            background=Colors.ACCENT,
            foreground=Colors.BG_PRIMARY,
        )
        style.map(
            "Accent.TButton",
            background=[("active", Colors.ACCENT_HOVER), ("pressed", Colors.ACCENT_HOVER)],
        )

        style.configure(
            "Nav.TButton",
            background=Colors.BG_SECONDARY,
            foreground=Colors.TEXT_SECONDARY,
            font=Fonts.BODY,
            padding=(Spacing.MD, Spacing.SM),
            anchor="w",
        )
        style.map(
            "Nav.TButton",
            background=[("active", Colors.BG_TERTIARY), ("selected", Colors.BG_TERTIARY)],
            foreground=[("active", Colors.TEXT_PRIMARY), ("selected", Colors.TEXT_PRIMARY)],
        )

        style.configure(
            "NavActive.TButton",
            background=Colors.BG_TERTIARY,
            foreground=Colors.TEXT_PRIMARY,
        )

        # Entry styles
        style.configure(
            "TEntry",
            fieldbackground=Colors.BG_INPUT,
            foreground=Colors.TEXT_PRIMARY,
            insertcolor=Colors.TEXT_PRIMARY,
            padding=Spacing.SM,
        )
        style.map(
            "TEntry",
            fieldbackground=[("focus", Colors.BG_TERTIARY)],
        )

        # Combobox styles
        style.configure(
            "TCombobox",
            fieldbackground=Colors.BG_INPUT,
            background=Colors.BG_TERTIARY,
            foreground=Colors.TEXT_PRIMARY,
            arrowcolor=Colors.TEXT_PRIMARY,
            selectbackground=Colors.BG_TERTIARY,
            selectforeground=Colors.TEXT_PRIMARY,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Colors.BG_INPUT)],
            foreground=[("readonly", Colors.TEXT_PRIMARY)],
            selectbackground=[("readonly", Colors.BG_TERTIARY)],
            selectforeground=[("readonly", Colors.TEXT_PRIMARY)],
        )

        # Style the combobox dropdown list (Tk Listbox, not ttk)
        root.option_add("*TCombobox*Listbox.background", Colors.BG_SECONDARY)
        root.option_add("*TCombobox*Listbox.foreground", Colors.TEXT_PRIMARY)
        root.option_add("*TCombobox*Listbox.selectBackground", Colors.ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", Colors.BG_PRIMARY)

        # Checkbutton styles
        style.configure(
            "TCheckbutton",
            background=Colors.BG_PRIMARY,
            foreground=Colors.TEXT_PRIMARY,
        )
        style.map(
            "TCheckbutton",
            background=[("active", Colors.BG_PRIMARY)],
        )

        # Scrollbar styles
        style.configure(
            "TScrollbar",
            background=Colors.BG_TERTIARY,
            troughcolor=Colors.BG_PRIMARY,
            arrowcolor=Colors.TEXT_MUTED,
        )

        # Treeview (table) styles
        style.configure(
            "Treeview",
            background=Colors.BG_PRIMARY,
            foreground=Colors.TEXT_PRIMARY,
            fieldbackground=Colors.BG_PRIMARY,
            rowheight=Sizes.TABLE_ROW_HEIGHT,
            font=Fonts.BODY,
        )
        style.configure(
            "Treeview.Heading",
            background=Colors.BG_SECONDARY,
            foreground=Colors.TEXT_PRIMARY,
            font=Fonts.BODY_BOLD,
        )
        style.map(
            "Treeview",
            background=[("selected", Colors.BG_TERTIARY)],
            foreground=[("selected", Colors.TEXT_PRIMARY)],
        )

        # Separator
        style.configure(
            "TSeparator",
            background=Colors.BORDER,
        )

        # Notebook (tabs)
        style.configure(
            "TNotebook",
            background=Colors.BG_PRIMARY,
        )
        style.configure(
            "TNotebook.Tab",
            background=Colors.BG_SECONDARY,
            foreground=Colors.TEXT_SECONDARY,
            padding=(Spacing.MD, Spacing.SM),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", Colors.BG_TERTIARY)],
            foreground=[("selected", Colors.TEXT_PRIMARY)],
        )

        # Progressbar
        style.configure(
            "TProgressbar",
            background=Colors.ACCENT,
            troughcolor=Colors.BG_SECONDARY,
        )

    @classmethod
    def apply_to_widget(cls, widget, background: str | None = None) -> None:
        """Apply theme colors to a raw tkinter widget."""
        bg = background or Colors.BG_PRIMARY
        try:
            widget.configure(
                bg=bg,
                fg=Colors.TEXT_PRIMARY,
                highlightbackground=Colors.BORDER,
                highlightcolor=Colors.ACCENT,
                insertbackground=Colors.TEXT_PRIMARY,
            )
        except Exception:
            # Some widgets don't support all options
            with contextlib.suppress(Exception):
                widget.configure(bg=bg)
