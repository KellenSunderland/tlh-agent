"""Tests for Claude AI service."""

from unittest.mock import patch

import pytest

from tlh_agent.services.claude import ClaudeService, Message, StreamEvent, ToolDefinition


class TestClaudeService:
    """Tests for ClaudeService."""

    @pytest.fixture
    def service(self) -> ClaudeService:
        """Create a ClaudeService instance."""
        with patch("tlh_agent.services.claude.anthropic.AsyncAnthropic"):
            return ClaudeService(api_key="test-key")

    def test_init_creates_client(self) -> None:
        """Test that initialization creates an Anthropic client."""
        with patch("tlh_agent.services.claude.anthropic.AsyncAnthropic") as mock_client:
            service = ClaudeService(api_key="test-key")

            mock_client.assert_called_once_with(api_key="test-key")
            assert service.api_key == "test-key"
            assert service.model == "claude-sonnet-4-5-20250929"

    def test_init_with_custom_model(self) -> None:
        """Test initialization with custom model."""
        with patch("tlh_agent.services.claude.anthropic.AsyncAnthropic"):
            service = ClaudeService(api_key="test-key", model="claude-3-opus-20240229")

            assert service.model == "claude-3-opus-20240229"

    def test_clear_history(self, service: ClaudeService) -> None:
        """Test clearing conversation history."""
        # Manually add some history
        service._history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
        ]

        service.clear_history()

        assert service._history == []

    def test_get_conversation_history_empty(self, service: ClaudeService) -> None:
        """Test getting empty conversation history."""
        result = service.get_conversation_history()

        assert result == []

    def test_get_conversation_history_with_messages(self, service: ClaudeService) -> None:
        """Test getting conversation history with messages."""
        service._history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
            {"role": "user", "content": "How are you?"},
        ]

        result = service.get_conversation_history()

        assert len(result) == 3
        assert result[0] == Message(role="user", content="Hello")
        assert result[1] == Message(role="assistant", content="Hi there!")
        assert result[2] == Message(role="user", content="How are you?")

    def test_get_conversation_history_with_tool_use(self, service: ClaudeService) -> None:
        """Test getting conversation history with tool use."""
        service._history = [
            {"role": "user", "content": "What's my portfolio value?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "tool-123",
                        "name": "get_portfolio",
                        "input": {},
                    },
                ],
            },
        ]

        result = service.get_conversation_history()

        assert len(result) == 2
        assert result[0] == Message(role="user", content="What's my portfolio value?")
        assert "Let me check" in result[1].content
        assert "get_portfolio" in result[1].content

    def test_set_system_prompt(self, service: ClaudeService) -> None:
        """Test setting custom system prompt."""
        new_prompt = "You are a helpful assistant."

        service.set_system_prompt(new_prompt)

        assert service._system_prompt == new_prompt


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_text_event(self) -> None:
        """Test creating a text event."""
        event = StreamEvent(type="text", text="Hello")

        assert event.type == "text"
        assert event.text == "Hello"
        assert event.tool_name is None
        assert event.tool_input is None

    def test_tool_use_event(self) -> None:
        """Test creating a tool use event."""
        event = StreamEvent(
            type="tool_use",
            tool_name="get_portfolio",
            tool_input={"ticker": "AAPL"},
            tool_use_id="tool-123",
        )

        assert event.type == "tool_use"
        assert event.tool_name == "get_portfolio"
        assert event.tool_input == {"ticker": "AAPL"}
        assert event.tool_use_id == "tool-123"

    def test_message_done_event(self) -> None:
        """Test creating a message done event."""
        event = StreamEvent(type="message_done")

        assert event.type == "message_done"
        assert event.text is None


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_tool_definition(self) -> None:
        """Test creating a tool definition."""
        tool = ToolDefinition(
            name="get_positions",
            description="Get all portfolio positions",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        assert tool.name == "get_positions"
        assert tool.description == "Get all portfolio positions"
        assert tool.input_schema["type"] == "object"


class TestMessage:
    """Tests for Message dataclass."""

    def test_user_message(self) -> None:
        """Test creating a user message."""
        msg = Message(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message(self) -> None:
        """Test creating an assistant message."""
        msg = Message(role="assistant", content="Hi there!")

        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
