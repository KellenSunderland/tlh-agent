"""Assistant pane component for Claude chat interface."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from tlh_agent.ui.components.chat_message import ChatMessage, StreamingMessage, ToolUseMessage
from tlh_agent.ui.theme import Colors, Fonts, Spacing


class AssistantPane(tk.Frame):
    """Right-side pane for Claude assistant chat.

    Provides a chat interface where users can interact with Claude
    to get portfolio insights and trade recommendations.
    """

    # Pane width
    WIDTH = 480

    def __init__(
        self,
        parent: tk.Widget,
        on_send: Callable[[str], None] | None = None,
        on_navigate: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        """Initialize the assistant pane.

        Args:
            parent: Parent widget.
            on_send: Callback when user sends a message.
            on_navigate: Callback to navigate to a screen (e.g., "harvest" for Trade Queue).
            **kwargs: Additional arguments for tk.Frame.
        """
        super().__init__(parent, bg=Colors.BG_SECONDARY, width=self.WIDTH, **kwargs)

        self._on_send = on_send
        self._on_navigate = on_navigate
        self._messages: list[tk.Widget] = []
        self._current_streaming: StreamingMessage | None = None

        # Prevent resize
        self.pack_propagate(False)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the assistant pane UI."""
        # Left border for visual separation
        left_border = tk.Frame(self, bg=Colors.ACCENT, width=3)
        left_border.pack(side=tk.LEFT, fill=tk.Y)

        # Main content container
        main_content = tk.Frame(self, bg=Colors.BG_SECONDARY)
        main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main_content, bg=Colors.BG_TERTIARY)
        header.pack(fill=tk.X)

        header_content = tk.Frame(header, bg=Colors.BG_TERTIARY, padx=Spacing.MD, pady=Spacing.SM)
        header_content.pack(fill=tk.X)

        tk.Label(
            header_content,
            text="Claude Assistant",
            font=Fonts.SUBHEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_TERTIARY,
        ).pack(side=tk.LEFT)

        # Clear button
        self.clear_btn = tk.Button(
            header_content,
            text="Clear",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_TERTIARY,
            activebackground=Colors.BG_SECONDARY,
            activeforeground=Colors.TEXT_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_clear,
        )
        self.clear_btn.pack(side=tk.RIGHT)

        # Chat area (scrollable)
        chat_container = tk.Frame(main_content, bg=Colors.BG_PRIMARY)
        chat_container.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling
        self.canvas = tk.Canvas(
            chat_container,
            bg=Colors.BG_PRIMARY,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            chat_container,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Frame inside canvas for messages
        self.messages_frame = tk.Frame(self.canvas, bg=Colors.BG_PRIMARY)
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.messages_frame,
            anchor=tk.NW,
        )

        # Bind resize events
        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Enable mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Input area
        input_container = tk.Frame(
            main_content, bg=Colors.BG_SECONDARY, padx=Spacing.SM, pady=Spacing.SM
        )
        input_container.pack(fill=tk.X, side=tk.BOTTOM)

        # Text entry
        self.input_entry = tk.Entry(
            input_container,
            font=Fonts.BODY,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_INPUT,
            insertbackground=Colors.TEXT_PRIMARY,
            relief=tk.FLAT,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, Spacing.SM), ipady=6)
        self.input_entry.bind("<Return>", self._on_enter)

        # Send button
        self.send_btn = tk.Button(
            input_container,
            text="Send",
            font=Fonts.BODY_BOLD,
            fg=Colors.BG_PRIMARY,
            bg=Colors.ACCENT,
            activebackground=Colors.ACCENT_HOVER,
            activeforeground=Colors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=Spacing.MD,
            pady=Spacing.XS,
            cursor="hand2",
            command=self._send_message,
        )
        self.send_btn.pack(side=tk.RIGHT)

        # Add welcome message
        self._add_welcome_message()

    def _add_welcome_message(self) -> None:
        """Add initial welcome message."""
        welcome = (
            "Hi! I'm your tax-loss harvesting assistant. I can help you:\n\n"
            "- Review your portfolio\n"
            "- Find harvest opportunities\n"
            "- Suggest S&P 500 tracking trades\n"
            "- Explain wash sale rules\n\n"
            "What would you like to do?"
        )
        self.add_assistant_message(welcome)

    def _on_frame_configure(self, event=None) -> None:
        """Update scroll region when frame size changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event=None) -> None:
        """Update frame width when canvas resizes."""
        if event:
            self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        """Handle mouse wheel scrolling."""
        # Only scroll if mouse is over this widget
        widget = event.widget
        while widget:
            if widget == self:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                break
            widget = widget.master if hasattr(widget, "master") else None

    def _on_enter(self, event=None) -> None:
        """Handle Enter key in input."""
        self._send_message()

    def _send_message(self) -> None:
        """Send the current input message."""
        message = self.input_entry.get().strip()
        if not message:
            return

        # Clear input
        self.input_entry.delete(0, tk.END)

        # Add user message
        self.add_user_message(message)

        # Call handler
        if self._on_send:
            self._on_send(message)

    def _on_clear(self) -> None:
        """Clear all messages."""
        for widget in self._messages:
            widget.destroy()
        self._messages.clear()
        self._current_streaming = None

        # Re-add welcome message
        self._add_welcome_message()

    def add_user_message(self, text: str) -> ChatMessage:
        """Add a user message to the chat.

        Args:
            text: Message text.

        Returns:
            The created message widget.
        """
        msg = ChatMessage(
            self.messages_frame,
            message=text,
            role="user",
        )
        msg.pack(fill=tk.X, padx=Spacing.SM)
        self._messages.append(msg)
        self._scroll_to_bottom()
        return msg

    def add_assistant_message(self, text: str) -> ChatMessage:
        """Add an assistant message to the chat.

        Args:
            text: Message text.

        Returns:
            The created message widget.
        """
        msg = ChatMessage(
            self.messages_frame,
            message=text,
            role="assistant",
        )
        msg.pack(fill=tk.X, padx=Spacing.SM)
        self._messages.append(msg)
        self._scroll_to_bottom()
        return msg

    def start_streaming_message(self, initial_text: str = "") -> StreamingMessage:
        """Start a streaming assistant message.

        Args:
            initial_text: Initial text to show.

        Returns:
            The streaming message widget.
        """
        self._current_streaming = StreamingMessage(
            self.messages_frame,
            initial_text=initial_text,
        )
        self._current_streaming.pack(fill=tk.X, padx=Spacing.SM)
        self._messages.append(self._current_streaming)
        self._scroll_to_bottom()
        return self._current_streaming

    def update_streaming_message(self, text: str) -> None:
        """Update the current streaming message.

        Args:
            text: Text to append or set.
        """
        if self._current_streaming:
            self._current_streaming.set_text(text)
            self._scroll_to_bottom()

    def finish_streaming_message(self) -> None:
        """Mark the streaming message as complete."""
        self._current_streaming = None

    def add_tool_use(self, tool_name: str) -> ToolUseMessage:
        """Add a tool use indicator.

        Args:
            tool_name: Name of the tool.

        Returns:
            The tool use widget.
        """
        msg = ToolUseMessage(
            self.messages_frame,
            tool_name=tool_name,
            status="running",
        )
        msg.pack(fill=tk.X, padx=Spacing.SM)
        self._messages.append(msg)
        self._scroll_to_bottom()
        return msg

    def add_action_button(self, text: str, action: str) -> tk.Button:
        """Add an action button (e.g., "View Queue").

        Args:
            text: Button text.
            action: Screen name to navigate to.

        Returns:
            The button widget.
        """
        container = tk.Frame(self.messages_frame, bg=Colors.BG_PRIMARY)
        container.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        btn = tk.Button(
            container,
            text=text,
            font=Fonts.BODY,
            fg=Colors.ACCENT,
            bg=Colors.BG_PRIMARY,
            activebackground=Colors.BG_SECONDARY,
            activeforeground=Colors.ACCENT_HOVER,
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._on_navigate(action) if self._on_navigate else None,
        )
        btn.pack(side=tk.LEFT)
        self._messages.append(container)
        self._scroll_to_bottom()
        return btn

    def _scroll_to_bottom(self) -> None:
        """Scroll chat to bottom."""
        self.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable input.

        Args:
            enabled: Whether to enable input.
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self.input_entry.configure(state=state)
        self.send_btn.configure(state=state)

    def show_thinking(self, text: str = "Thinking...") -> None:
        """Show a thinking indicator.

        Args:
            text: Text to show (e.g., "Thinking..." or "Using get_positions...").
        """
        self.hide_thinking()  # Remove any existing indicator
        self._thinking_frame = tk.Frame(self.messages_frame, bg=Colors.BG_PRIMARY)
        self._thinking_frame.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        indicator = tk.Frame(
            self._thinking_frame,
            bg=Colors.BG_TERTIARY,
            padx=Spacing.SM,
            pady=Spacing.XS,
        )
        indicator.pack(side=tk.LEFT)

        self._thinking_label = tk.Label(
            indicator,
            text=f"⏳ {text}",
            font=Fonts.CAPTION,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_TERTIARY,
        )
        self._thinking_label.pack()
        self._scroll_to_bottom()

    def update_thinking(self, text: str) -> None:
        """Update the thinking indicator text.

        Args:
            text: New text to show.
        """
        if hasattr(self, "_thinking_label") and self._thinking_label:
            self._thinking_label.configure(text=f"⏳ {text}")
            self._scroll_to_bottom()

    def hide_thinking(self) -> None:
        """Hide the thinking indicator."""
        if hasattr(self, "_thinking_frame") and self._thinking_frame:
            self._thinking_frame.destroy()
            self._thinking_frame = None
            self._thinking_label = None
