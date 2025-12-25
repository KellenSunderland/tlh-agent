"""Chat message bubble component for the assistant pane."""

import tkinter as tk

from tlh_agent.ui.theme import Colors, Fonts, Spacing


class ChatMessage(tk.Frame):
    """A chat message bubble.

    Displays messages with different styling for user vs assistant messages.
    """

    def __init__(
        self,
        parent: tk.Widget,
        message: str,
        role: str,
        **kwargs,
    ) -> None:
        """Initialize the chat message.

        Args:
            parent: Parent widget.
            message: The message text.
            role: "user" or "assistant".
            **kwargs: Additional arguments for tk.Frame.
        """
        super().__init__(parent, bg=Colors.BG_PRIMARY, **kwargs)

        self._role = role
        self._is_user = role == "user"

        # Container for alignment
        self.container = tk.Frame(self, bg=Colors.BG_PRIMARY)
        self.container.pack(
            fill=tk.X,
            anchor=tk.E if self._is_user else tk.W,
            pady=Spacing.XS,
        )

        # Bubble styling based on role
        if self._is_user:
            bg_color = Colors.ACCENT
            text_color = Colors.BG_PRIMARY
            anchor = tk.E
        else:
            bg_color = Colors.BG_SECONDARY
            text_color = Colors.TEXT_PRIMARY
            anchor = tk.W

        # Message bubble
        self.bubble = tk.Frame(
            self.container,
            bg=bg_color,
            padx=Spacing.MD,
            pady=Spacing.SM,
        )
        self.bubble.pack(side=tk.RIGHT if self._is_user else tk.LEFT, anchor=anchor)

        # Message text
        self.text_label = tk.Label(
            self.bubble,
            text=message,
            font=Fonts.BODY,
            fg=text_color,
            bg=bg_color,
            wraplength=400,  # Max width for message bubble
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self.text_label.pack(anchor=tk.W)

    @property
    def role(self) -> str:
        """Get the message role."""
        return self._role

    def update_text(self, text: str) -> None:
        """Update the message text.

        Args:
            text: New message text.
        """
        self.text_label.configure(text=text)


class StreamingMessage(ChatMessage):
    """A chat message that supports streaming updates.

    Used for assistant messages that are being typed/streamed.
    """

    def __init__(
        self,
        parent: tk.Widget,
        initial_text: str = "",
        **kwargs,
    ) -> None:
        """Initialize the streaming message.

        Args:
            parent: Parent widget.
            initial_text: Initial message text.
            **kwargs: Additional arguments for ChatMessage.
        """
        super().__init__(parent, initial_text or "...", role="assistant", **kwargs)
        self._full_text = initial_text

    def append_text(self, text: str) -> None:
        """Append text to the message.

        Args:
            text: Text to append.
        """
        self._full_text += text
        self.text_label.configure(text=self._full_text)

    def set_text(self, text: str) -> None:
        """Set the full message text.

        Args:
            text: Complete message text.
        """
        self._full_text = text
        self.text_label.configure(text=text)

    @property
    def full_text(self) -> str:
        """Get the full message text."""
        return self._full_text


class ToolUseMessage(tk.Frame):
    """A message showing tool use activity.

    Displays when the assistant is using a tool.
    """

    def __init__(
        self,
        parent: tk.Widget,
        tool_name: str,
        status: str = "running",
        **kwargs,
    ) -> None:
        """Initialize the tool use message.

        Args:
            parent: Parent widget.
            tool_name: Name of the tool being used.
            status: "running", "done", or "error".
            **kwargs: Additional arguments for tk.Frame.
        """
        super().__init__(parent, bg=Colors.BG_PRIMARY, **kwargs)

        self._tool_name = tool_name
        self._status = status

        # Container
        self.container = tk.Frame(self, bg=Colors.BG_PRIMARY)
        self.container.pack(fill=tk.X, pady=Spacing.XS)

        # Tool indicator
        self.indicator = tk.Frame(
            self.container,
            bg=Colors.BG_TERTIARY,
            padx=Spacing.SM,
            pady=Spacing.XS,
        )
        self.indicator.pack(side=tk.LEFT)

        # Icon and text
        status_icons = {
            "running": "...",
            "done": " ",
            "error": " ",
        }
        status_colors = {
            "running": Colors.TEXT_MUTED,
            "done": Colors.SUCCESS_TEXT,
            "error": Colors.DANGER_TEXT,
        }

        icon = status_icons.get(status, "...")
        color = status_colors.get(status, Colors.TEXT_MUTED)

        self.label = tk.Label(
            self.indicator,
            text=f"{icon} Using {tool_name}",
            font=Fonts.CAPTION,
            fg=color,
            bg=Colors.BG_TERTIARY,
        )
        self.label.pack()

    def set_status(self, status: str) -> None:
        """Update the tool use status.

        Args:
            status: "running", "done", or "error".
        """
        self._status = status

        status_icons = {
            "running": "...",
            "done": " ",
            "error": " ",
        }
        status_colors = {
            "running": Colors.TEXT_MUTED,
            "done": Colors.SUCCESS_TEXT,
            "error": Colors.DANGER_TEXT,
        }

        icon = status_icons.get(status, "...")
        color = status_colors.get(status, Colors.TEXT_MUTED)

        self.label.configure(text=f"{icon} Using {self._tool_name}", fg=color)
