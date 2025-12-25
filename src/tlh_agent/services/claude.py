"""Claude AI service for TLH Agent.

Provides Claude AI integration for natural language portfolio commands
and trade recommendations.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anthropic
from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)

# Logger is configured by assistant.py which adds the file handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@dataclass
class Message:
    """A chat message."""

    role: str  # "user" or "assistant"
    content: str


@dataclass
class StreamEvent:
    """An event from the Claude streaming API."""

    type: str  # "text", "tool_use", "tool_result", "message_done"
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_use_id: str | None = None


@dataclass
class ToolDefinition:
    """A tool that Claude can use."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ClaudeService:
    """Service for interacting with Claude AI.

    Provides streaming message API with tool use support
    for portfolio commands and trade recommendations.
    """

    api_key: str
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 16384  # Need more tokens to generate 503 trades
    _client: anthropic.AsyncAnthropic = field(init=False, repr=False)
    _history: list[MessageParam] = field(default_factory=list, repr=False)
    _system_prompt: str = field(
        default="""You are the AI assistant for a TAX-LOSS HARVESTING DIRECT INDEXING application.

GOAL:
Replicate Wealthfront-style direct indexing without fees. Tax-loss harvesting sells
investments below cost basis to realize losses that offset gains. Direct indexing
means owning ALL individual stocks (not ETFs) to enable stock-level TLH.

AVAILABLE TOOLS:
- get_portfolio_summary: Get total value, gains/losses, harvest opportunity count
- get_positions: List all current holdings with cost basis and gains
- get_harvest_opportunities: Find positions with unrealized losses eligible for harvesting
- get_index_allocation: Get S&P 500 stocks with target weights (for reference only)
- get_rebalance_plan: Tax-aware rebalancing recommendations respecting wash sales
- get_trade_queue: View pending trades in the queue (can filter by symbol)
- buy_index: Buy ALL stocks in an index - pass investment_amount and optional index name
- propose_trades: Add individual trades to the queue (for harvest/rebalance, NOT index buys)
- clear_trade_queue: Clear/cancel all pending trades from the queue
- remove_trade: Remove trades for a specific symbol from the queue

SUPPORTED INDEXES (for buy_index):
- sp500: S&P 500 (500 large-cap stocks) - FULLY IMPLEMENTED
- nasdaq100: Nasdaq 100 (100 tech-heavy stocks) - coming soon
- dowjones: Dow Jones Industrial Average (30 blue-chip stocks) - coming soon
- russell1000: Russell 1000 (1000 large-cap stocks) - coming soon
- russell2000: Russell 2000 (2000 small-cap stocks) - coming soon
- russell3000: Russell 3000 (3000 total market stocks) - coming soon

CRITICAL RULES:
1. NEVER suggest ETFs (SPY, VOO, IVV, QQQ, DIA, IWM). This app is for DIRECT INDEXING.
2. For index investments, use buy_index(amount, index) - creates all trades.
3. Users approve trades from the Trade Queue screen.
4. Be action-oriented. Execute, don't ask for confirmation.
5. Only use ONE tool at a time.

Be concise in responses.""",
        repr=False,
    )

    def __post_init__(self) -> None:
        """Initialize the Anthropic client."""
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def send_message(
        self,
        message: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Send a message to Claude and stream the response.

        Args:
            message: The user's message.
            tools: Optional list of tools Claude can use.

        Yields:
            StreamEvent objects as the response streams in.
        """
        # Add user message to history
        logger.info("=== CLAUDE SEND_MESSAGE START ===")
        logger.debug(f"User message: {message[:100]}...")
        self._history.append({"role": "user", "content": message})

        # Build tools for API
        api_tools: list[ToolParam] | None = None
        if tools:
            api_tools = [
                ToolParam(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )
                for tool in tools
            ]
            logger.debug(f"Tools provided: {[t.name for t in tools]}")
        else:
            logger.debug("No tools provided")

        # Create streaming message
        logger.info(f"Creating streaming message with model={self.model}")
        stream_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self._system_prompt,
            "messages": self._history,
        }
        if api_tools is not None:
            stream_kwargs["tools"] = api_tools

        async with self._client.messages.stream(**stream_kwargs) as stream:
            logger.debug("Stream opened successfully")
            assistant_content: list[ContentBlockParam] = []
            current_text = ""
            current_tool_use: dict[str, Any] | None = None
            event_count = 0

            async for event in stream:
                event_count += 1
                logger.debug(f"Stream event #{event_count}: type={event.type}")
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        current_text = ""
                    elif event.content_block.type == "tool_use":
                        current_tool_use = {
                            "type": "tool_use",
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": {},
                        }

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        text_chunk = str(getattr(delta, "text", ""))
                        current_text += text_chunk
                        yield StreamEvent(type="text", text=text_chunk)
                    elif hasattr(delta, "partial_json"):
                        # Tool input is streamed as partial JSON
                        pass

                elif event.type == "content_block_stop":
                    if current_text:
                        assistant_content.append(TextBlockParam(type="text", text=current_text))
                    if current_tool_use:
                        # Get the full tool input from the accumulated message
                        pass

                elif event.type == "message_stop":
                    # Get the final message to extract tool use
                    logger.info("message_stop received, getting final message...")
                    final_message = await stream.get_final_message()
                    logger.debug(f"Final message content blocks: {len(final_message.content)}")
                    for block in final_message.content:
                        logger.debug(f"Processing block type: {block.type}")
                        if block.type == "tool_use":
                            logger.info(f"=== TOOL_USE DETECTED: {block.name} ===")
                            logger.debug(f"Tool ID: {block.id}")
                            logger.debug(f"Tool input: {block.input}")
                            yield StreamEvent(
                                type="tool_use",
                                tool_name=block.name,
                                tool_input=dict(block.input),
                                tool_use_id=block.id,
                            )
                            logger.debug(f"Yielded tool_use StreamEvent for {block.name}")
                            assistant_content.append(
                                ToolUseBlockParam(
                                    type="tool_use",
                                    id=block.id,
                                    name=block.name,
                                    input=dict(block.input),
                                )
                            )

                    # Add assistant message to history
                    if assistant_content:
                        self._history.append({"role": "assistant", "content": assistant_content})
                        logger.debug(f"Added {len(assistant_content)} blocks to history")

                    logger.info(f"=== CLAUDE SEND_MESSAGE COMPLETE (events: {event_count}) ===")
                    yield StreamEvent(type="message_done")

    async def add_tool_result(
        self,
        tool_use_id: str,
        result: str,
        is_error: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        """Add a tool result and continue the conversation.

        Args:
            tool_use_id: The ID of the tool use to respond to.
            result: The result of the tool execution.
            is_error: Whether the tool execution resulted in an error.

        Yields:
            StreamEvent objects as Claude processes the result.
        """
        # Add tool result to history
        logger.info("=== CLAUDE ADD_TOOL_RESULT START ===")
        logger.debug(f"Tool use ID: {tool_use_id}")
        logger.debug(f"Result length: {len(result)}")
        logger.debug(f"Is error: {is_error}")
        tool_result_block = ToolResultBlockParam(
            type="tool_result",
            tool_use_id=tool_use_id,
            content=result,
            is_error=is_error,
        )
        self._history.append(
            MessageParam(role="user", content=[tool_result_block])
        )
        logger.debug("Tool result added to history")

        # Continue the conversation
        logger.info("Continuing conversation with tool result...")
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt,
            messages=self._history,
        ) as stream:
            logger.debug("Tool result stream opened successfully")
            assistant_content: list[ContentBlockParam] = []
            current_text = ""
            event_count = 0

            async for event in stream:
                event_count += 1
                logger.debug(f"Tool result stream event #{event_count}: type={event.type}")
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        current_text = ""

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        text_chunk = str(getattr(delta, "text", ""))
                        current_text += text_chunk
                        yield StreamEvent(type="text", text=text_chunk)

                elif event.type == "content_block_stop":
                    if current_text:
                        assistant_content.append(TextBlockParam(type="text", text=current_text))

                elif event.type == "message_stop":
                    # Get final message to check for more tool uses
                    logger.info("Tool result message_stop received, getting final message...")
                    final_message = await stream.get_final_message()
                    logger.debug(f"Final message blocks: {len(final_message.content)}")
                    for block in final_message.content:
                        logger.debug(f"Processing block type: {block.type}")
                        if block.type == "tool_use":
                            logger.info(f"=== FOLLOW-UP TOOL_USE DETECTED: {block.name} ===")
                            yield StreamEvent(
                                type="tool_use",
                                tool_name=block.name,
                                tool_input=dict(block.input),
                                tool_use_id=block.id,
                            )
                            assistant_content.append(
                                ToolUseBlockParam(
                                    type="tool_use",
                                    id=block.id,
                                    name=block.name,
                                    input=dict(block.input),
                                )
                            )

                    if assistant_content:
                        self._history.append({"role": "assistant", "content": assistant_content})
                        logger.debug(f"Added {len(assistant_content)} tool result blocks")

                    logger.info(f"=== CLAUDE ADD_TOOL_RESULT COMPLETE (events: {event_count}) ===")
                    yield StreamEvent(type="message_done")

    def get_conversation_history(self) -> list[Message]:
        """Get the conversation history.

        Returns:
            List of messages in the conversation.
        """
        messages = []
        for msg in self._history:
            role = msg["role"]
            content = msg["content"]

            # Handle different content formats
            if isinstance(content, str):
                messages.append(Message(role=role, content=content))
            elif isinstance(content, list):
                # Extract text content
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif item.get("type") == "tool_use":
                            text_parts.append(f"[Using tool: {item.get('name')}]")
                        elif item.get("type") == "tool_result":
                            text_parts.append("[Tool result]")
                if text_parts:
                    messages.append(Message(role=role, content=" ".join(text_parts)))

        return messages

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history = []

    def set_system_prompt(self, prompt: str) -> None:
        """Set a custom system prompt.

        Args:
            prompt: The new system prompt.
        """
        self._system_prompt = prompt
