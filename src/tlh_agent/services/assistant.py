"""Assistant controller for Claude integration.

Connects the UI to ClaudeService and handles tool execution.
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tlh_agent.services.claude import ClaudeService, StreamEvent
from tlh_agent.services.claude_tools import ClaudeToolProvider

logger = logging.getLogger(__name__)


@dataclass
class AssistantState:
    """Current state of the assistant."""

    is_processing: bool = False
    current_tool: str | None = None
    error: str | None = None


class AssistantController:
    """Controller for Claude assistant interactions.

    Handles:
    - Sending messages to Claude
    - Processing streaming responses
    - Executing tools and sending results back
    - Managing conversation state
    """

    def __init__(
        self,
        claude_service: ClaudeService,
        tool_provider: ClaudeToolProvider,
    ) -> None:
        """Initialize the assistant controller.

        Args:
            claude_service: The Claude API service.
            tool_provider: Provider for portfolio tools.
        """
        self._claude = claude_service
        self._tools = tool_provider
        self._state = AssistantState()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

        # Callbacks for UI updates
        self._on_text: Callable[[str], None] | None = None
        self._on_tool_use: Callable[[str], None] | None = None
        self._on_tool_done: Callable[[str, bool], None] | None = None
        self._on_done: Callable[[], None] | None = None
        self._on_error: Callable[[str], None] | None = None
        self._on_state_change: Callable[[AssistantState], None] | None = None

    def set_callbacks(
        self,
        on_text: Callable[[str], None] | None = None,
        on_tool_use: Callable[[str], None] | None = None,
        on_tool_done: Callable[[str, bool], None] | None = None,
        on_done: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_state_change: Callable[[AssistantState], None] | None = None,
    ) -> None:
        """Set UI callbacks.

        Args:
            on_text: Called with each text chunk as it streams.
            on_tool_use: Called when Claude starts using a tool.
            on_tool_done: Called when tool execution completes (name, success).
            on_done: Called when the full response is complete.
            on_error: Called if an error occurs.
            on_state_change: Called when state changes.
        """
        self._on_text = on_text
        self._on_tool_use = on_tool_use
        self._on_tool_done = on_tool_done
        self._on_done = on_done
        self._on_error = on_error
        self._on_state_change = on_state_change

    def send_message(self, message: str) -> None:
        """Send a message to Claude.

        This runs async processing in a background thread.

        Args:
            message: The user's message.
        """
        if self._state.is_processing:
            logger.warning("Already processing a message, ignoring")
            return

        self._update_state(is_processing=True, current_tool=None, error=None)

        # Run async code in a new thread with its own event loop
        self._thread = threading.Thread(
            target=self._run_async,
            args=(message,),
            daemon=True,
        )
        self._thread.start()

    def _run_async(self, message: str) -> None:
        """Run async message processing in a thread.

        Args:
            message: The user's message.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._process_message(message))
        except Exception as e:
            logger.exception("Error processing message")
            self._safe_callback(self._on_error, str(e))
        finally:
            self._loop.close()
            self._update_state(is_processing=False, current_tool=None)
            self._safe_callback(self._on_done)

    async def _process_message(self, message: str) -> None:
        """Process a message with tool execution loop.

        Args:
            message: The user's message.
        """
        tools = self._tools.get_tool_definitions()

        # Initial message
        pending_tool_uses: list[dict[str, Any]] = []

        async for event in self._claude.send_message(message, tools):
            await self._handle_event(event, pending_tool_uses)

        # Process any pending tool uses
        while pending_tool_uses:
            tool_use = pending_tool_uses.pop(0)
            await self._execute_tool_and_continue(tool_use, pending_tool_uses)

    async def _handle_event(
        self,
        event: StreamEvent,
        pending_tool_uses: list[dict[str, Any]],
    ) -> None:
        """Handle a stream event.

        Args:
            event: The stream event.
            pending_tool_uses: List to collect pending tool uses.
        """
        if event.type == "text" and event.text:
            self._safe_callback(self._on_text, event.text)

        elif event.type == "tool_use":
            pending_tool_uses.append({
                "id": event.tool_use_id,
                "name": event.tool_name,
                "input": event.tool_input,
            })
            self._update_state(current_tool=event.tool_name)
            self._safe_callback(self._on_tool_use, event.tool_name)

    async def _execute_tool_and_continue(
        self,
        tool_use: dict[str, Any],
        pending_tool_uses: list[dict[str, Any]],
    ) -> None:
        """Execute a tool and continue the conversation.

        Args:
            tool_use: The tool use to execute.
            pending_tool_uses: List to collect more pending tool uses.
        """
        tool_name = tool_use["name"]
        tool_input = tool_use["input"] or {}
        tool_use_id = tool_use["id"]

        logger.info(f"Executing tool: {tool_name}")

        # Execute the tool
        result = self._tools.execute_tool(tool_name, tool_input)

        is_success = result.success
        self._safe_callback(self._on_tool_done, tool_name, is_success)

        # Send result back to Claude
        async for event in self._claude.add_tool_result(
            tool_use_id=tool_use_id,
            result=result.to_json(),
            is_error=not result.success,
        ):
            await self._handle_event(event, pending_tool_uses)

        self._update_state(current_tool=None)

    def _update_state(self, **kwargs: Any) -> None:
        """Update state and notify listeners.

        Args:
            **kwargs: State fields to update.
        """
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)

        self._safe_callback(self._on_state_change, self._state)

    def _safe_callback(self, callback: Callable | None, *args: Any) -> None:
        """Safely call a callback, catching any exceptions.

        Args:
            callback: The callback to call.
            *args: Arguments to pass to the callback.
        """
        if callback:
            try:
                callback(*args)
            except Exception:
                logger.exception(f"Error in callback {callback}")

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._claude.clear_history()

    @property
    def is_processing(self) -> bool:
        """Check if currently processing a message."""
        return self._state.is_processing

    @property
    def state(self) -> AssistantState:
        """Get the current state."""
        return self._state
