"""Claude AI service for TLH Agent.

Provides Claude AI integration for natural language portfolio commands
and trade recommendations.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anthropic


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
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    _client: anthropic.AsyncAnthropic = field(init=False, repr=False)
    _history: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _system_prompt: str = field(
        default="""You are a helpful portfolio assistant for a tax-loss harvesting application.

Your job is to help users:
- Understand their portfolio positions and performance
- Find tax-loss harvesting opportunities
- Track S&P 500 index allocations
- Recommend and execute trades (with user approval)

Always be clear about the financial implications of any actions.
When proposing trades, explain the reasoning and tax impact.
Be concise but thorough in your responses.""",
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
        self._history.append({"role": "user", "content": message})

        # Build tools for API
        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        # Create streaming message
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt,
            messages=self._history,
            tools=api_tools or anthropic.NOT_GIVEN,
        ) as stream:
            assistant_content: list[dict[str, Any]] = []
            current_text = ""
            current_tool_use: dict[str, Any] | None = None

            async for event in stream:
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
                    if hasattr(event.delta, "text"):
                        current_text += event.delta.text
                        yield StreamEvent(type="text", text=event.delta.text)
                    elif hasattr(event.delta, "partial_json"):
                        # Tool input is streamed as partial JSON
                        pass

                elif event.type == "content_block_stop":
                    if current_text:
                        assistant_content.append({"type": "text", "text": current_text})
                    if current_tool_use:
                        # Get the full tool input from the accumulated message
                        pass

                elif event.type == "message_stop":
                    # Get the final message to extract tool use
                    final_message = await stream.get_final_message()
                    for block in final_message.content:
                        if block.type == "tool_use":
                            yield StreamEvent(
                                type="tool_use",
                                tool_name=block.name,
                                tool_input=dict(block.input),
                                tool_use_id=block.id,
                            )
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": block.name,
                                    "input": dict(block.input),
                                }
                            )

                    # Add assistant message to history
                    if assistant_content:
                        self._history.append({"role": "assistant", "content": assistant_content})

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
        self._history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                        "is_error": is_error,
                    }
                ],
            }
        )

        # Continue the conversation
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_prompt,
            messages=self._history,
        ) as stream:
            assistant_content: list[dict[str, Any]] = []
            current_text = ""

            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        current_text = ""

                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        current_text += event.delta.text
                        yield StreamEvent(type="text", text=event.delta.text)

                elif event.type == "content_block_stop":
                    if current_text:
                        assistant_content.append({"type": "text", "text": current_text})

                elif event.type == "message_stop":
                    # Get final message to check for more tool uses
                    final_message = await stream.get_final_message()
                    for block in final_message.content:
                        if block.type == "tool_use":
                            yield StreamEvent(
                                type="tool_use",
                                tool_name=block.name,
                                tool_input=dict(block.input),
                                tool_use_id=block.id,
                            )
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": block.name,
                                    "input": dict(block.input),
                                }
                            )

                    if assistant_content:
                        self._history.append({"role": "assistant", "content": assistant_content})

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
