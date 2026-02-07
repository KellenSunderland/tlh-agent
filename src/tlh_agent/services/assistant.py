"""Assistant controller for Claude integration.

Connects the UI to ClaudeService and handles tool execution.
"""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from tlh_agent.services.claude import ClaudeService, StreamEvent
from tlh_agent.services.claude_tools import ClaudeToolProvider

# Set up dedicated log file for agent debugging
LOG_FILE = Path.home() / ".tlh-agent" / "agent.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Create file handler for agent-specific logging
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Also add to claude service, tools, execution, and UI loggers
logging.getLogger('tlh_agent.services.claude').setLevel(logging.DEBUG)
logging.getLogger('tlh_agent.services.claude').addHandler(file_handler)
logging.getLogger('tlh_agent.services.claude_tools').setLevel(logging.DEBUG)
logging.getLogger('tlh_agent.services.claude_tools').addHandler(file_handler)
logging.getLogger('tlh_agent.services.execution').setLevel(logging.DEBUG)
logging.getLogger('tlh_agent.services.execution').addHandler(file_handler)
logging.getLogger('tlh_agent.ui.screens').setLevel(logging.DEBUG)
logging.getLogger('tlh_agent.ui.screens').addHandler(file_handler)

# Add business logic module loggers
for _module in [
    'tlh_agent.services.scanner',
    'tlh_agent.services.portfolio',
    'tlh_agent.services.rules',
    'tlh_agent.services.wash_sale',
    'tlh_agent.services.trade_queue',
    'tlh_agent.services.rebalance',
    'tlh_agent.brokers.alpaca',
]:
    logging.getLogger(_module).setLevel(logging.DEBUG)
    logging.getLogger(_module).addHandler(file_handler)


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
        logger.info("=== SEND_MESSAGE START ===")
        logger.info(f"User message: {message[:100]}...")

        if self._state.is_processing:
            logger.warning("Already processing a message, ignoring")
            return

        self._update_state(is_processing=True, current_tool=None, error=None)
        logger.debug("State updated to processing=True")

        # Run async code in a new thread with its own event loop
        self._thread = threading.Thread(
            target=self._run_async,
            args=(message,),
            daemon=True,
        )
        logger.debug("Starting async thread...")
        self._thread.start()
        logger.debug("Async thread started")

    def _run_async(self, message: str) -> None:
        """Run async message processing in a thread.

        Args:
            message: The user's message.
        """
        logger.info("=== RUN_ASYNC START ===")
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        max_retries = 3
        base_delay = 30  # seconds

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Running _process_message in event loop (attempt {attempt + 1})...")
                self._loop.run_until_complete(self._process_message(message))
                logger.info("=== RUN_ASYNC COMPLETE (success) ===")
                break  # Success, exit retry loop
            except anthropic.RateLimitError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {delay}s before retry...")
                    self._safe_callback(
                        self._on_text,
                        f"\n\n⏳ Rate limit reached. Waiting {delay} seconds before retrying...\n"
                    )
                    time.sleep(delay)
                    self._safe_callback(self._on_text, "Retrying...\n")
                else:
                    logger.error(f"Rate limit exceeded after {max_retries} retries")
                    self._safe_callback(
                        self._on_error,
                        "Rate limit exceeded. Please wait a minute and try again."
                    )
            except Exception as e:
                logger.exception(f"Error processing message: {e}")
                self._safe_callback(self._on_error, str(e))
                break  # Don't retry non-rate-limit errors

        logger.debug("Closing event loop...")
        self._loop.close()
        self._update_state(is_processing=False, current_tool=None)
        logger.debug("Calling on_done callback...")
        self._safe_callback(self._on_done)
        logger.info("=== RUN_ASYNC FINALLY COMPLETE ===")

    async def _process_message(self, message: str) -> None:
        """Process a message with tool execution loop.

        Args:
            message: The user's message.
        """
        logger.info("=== PROCESS_MESSAGE START ===")
        tools = self._tools.get_tool_definitions()
        logger.debug(f"Got {len(tools)} tool definitions")

        # Initial message
        pending_tool_uses: list[dict[str, Any]] = []

        logger.info("Sending message to Claude API...")
        event_count = 0
        async for event in self._claude.send_message(message, tools):
            event_count += 1
            logger.debug(f"Received event #{event_count}: type={event.type}")
            await self._handle_event(event, pending_tool_uses)

        logger.info(f"Finished receiving events. Total: {event_count}")
        logger.info(f"Pending tool uses: {len(pending_tool_uses)}")

        # Process any pending tool uses (all must be sent back together)
        while pending_tool_uses:
            batch = list(pending_tool_uses)
            pending_tool_uses.clear()
            logger.info(f"Processing {len(batch)} tool use(s) as a batch")
            await self._execute_tools_and_continue(batch, pending_tool_uses)

        logger.info("=== PROCESS_MESSAGE COMPLETE ===")

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
            text_preview = event.text[:50] + "..." if len(event.text) > 50 else event.text
            logger.debug(f"Text event: {text_preview}")
            self._safe_callback(self._on_text, event.text)

        elif event.type == "tool_use":
            logger.info(f"=== TOOL_USE EVENT: {event.tool_name} ===")
            logger.debug(f"Tool ID: {event.tool_use_id}")
            logger.debug(f"Tool input: {event.tool_input}")
            pending_tool_uses.append({
                "id": event.tool_use_id,
                "name": event.tool_name,
                "input": event.tool_input,
            })
            self._update_state(current_tool=event.tool_name)
            self._safe_callback(self._on_tool_use, event.tool_name)

    async def _execute_tools_and_continue(
        self,
        tool_uses: list[dict[str, Any]],
        pending_tool_uses: list[dict[str, Any]],
    ) -> None:
        """Execute all tool uses and send results back to Claude together.

        The Anthropic API requires all tool results from parallel tool calls
        to be sent in a single user message.

        Args:
            tool_uses: The tool uses to execute.
            pending_tool_uses: List to collect more pending tool uses from the response.
        """
        # Execute all tools and collect results
        all_results = []
        for tool_use in tool_uses:
            tool_name = tool_use["name"]
            tool_input = tool_use["input"] or {}
            tool_use_id = tool_use["id"]

            logger.info(f"=== EXECUTE_TOOL: {tool_name} ===")
            logger.debug(f"Tool ID: {tool_use_id}, input: {tool_input}")

            self._update_state(current_tool=tool_name)
            result = self._tools.execute_tool(tool_name, tool_input)
            logger.info(f"Tool result: success={result.success}")
            if not result.success:
                logger.error(f"Tool error: {result.error}")
            else:
                logger.debug(f"Tool data: {str(result.data)[:200]}...")

            self._safe_callback(self._on_tool_done, tool_name, result.success)

            all_results.append({
                "tool_use_id": tool_use_id,
                "result": result.to_json(),
                "is_error": not result.success,
            })

        # Send all results back to Claude in one message
        logger.info(f"Sending {len(all_results)} tool result(s) back to Claude...")
        event_count = 0
        async for event in self._claude.add_tool_results(all_results):
            event_count += 1
            logger.debug(f"Tool result event #{event_count}: type={event.type}")
            await self._handle_event(event, pending_tool_uses)

        logger.info(f"Tool result events received: {event_count}")
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
