"""Tests for the assistant controller."""

from unittest.mock import MagicMock

import pytest

from tlh_agent.services.assistant import AssistantController, AssistantState
from tlh_agent.services.claude import ClaudeService
from tlh_agent.services.tools import ClaudeToolProvider, ToolResult


class TestAssistantState:
    """Tests for AssistantState dataclass."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = AssistantState()

        assert state.is_processing is False
        assert state.current_tool is None
        assert state.error is None

    def test_custom_state(self) -> None:
        """Test custom state values."""
        state = AssistantState(
            is_processing=True,
            current_tool="get_positions",
            error="Something went wrong",
        )

        assert state.is_processing is True
        assert state.current_tool == "get_positions"
        assert state.error == "Something went wrong"


class TestAssistantController:
    """Tests for AssistantController."""

    @pytest.fixture
    def mock_claude_service(self) -> MagicMock:
        """Create a mock Claude service."""
        service = MagicMock(spec=ClaudeService)
        return service

    @pytest.fixture
    def mock_tool_provider(self) -> MagicMock:
        """Create a mock tool provider."""
        provider = MagicMock(spec=ClaudeToolProvider)
        provider.get_tool_definitions.return_value = []
        provider.execute_tool.return_value = ToolResult(
            success=True,
            data={"key": "value"},
        )
        return provider

    @pytest.fixture
    def controller(
        self,
        mock_claude_service: MagicMock,
        mock_tool_provider: MagicMock,
    ) -> AssistantController:
        """Create an assistant controller with mocked services."""
        return AssistantController(
            claude_service=mock_claude_service,
            tool_provider=mock_tool_provider,
        )

    def test_init(self, controller: AssistantController) -> None:
        """Test controller initialization."""
        assert controller.is_processing is False
        assert controller.state.current_tool is None

    def test_set_callbacks(self, controller: AssistantController) -> None:
        """Test setting callbacks."""
        on_text = MagicMock()
        on_done = MagicMock()

        controller.set_callbacks(on_text=on_text, on_done=on_done)

        # Callbacks should be stored but not called yet
        on_text.assert_not_called()
        on_done.assert_not_called()

    def test_clear_history(
        self,
        controller: AssistantController,
        mock_claude_service: MagicMock,
    ) -> None:
        """Test clearing history."""
        controller.clear_history()

        mock_claude_service.clear_history.assert_called_once()

    def test_is_processing_property(self, controller: AssistantController) -> None:
        """Test is_processing property."""
        assert controller.is_processing is False

        controller._state.is_processing = True
        assert controller.is_processing is True

    def test_state_property(self, controller: AssistantController) -> None:
        """Test state property."""
        state = controller.state

        assert isinstance(state, AssistantState)
        assert state.is_processing is False

    def test_update_state(self, controller: AssistantController) -> None:
        """Test _update_state method."""
        on_state_change = MagicMock()
        controller.set_callbacks(on_state_change=on_state_change)

        controller._update_state(is_processing=True, current_tool="test_tool")

        assert controller.state.is_processing is True
        assert controller.state.current_tool == "test_tool"
        on_state_change.assert_called_once()

    def test_safe_callback_handles_errors(
        self,
        controller: AssistantController,
    ) -> None:
        """Test that _safe_callback handles exceptions."""
        failing_callback = MagicMock(side_effect=Exception("Test error"))

        # Should not raise
        controller._safe_callback(failing_callback, "arg1", "arg2")

        failing_callback.assert_called_once_with("arg1", "arg2")

    def test_safe_callback_with_none(self, controller: AssistantController) -> None:
        """Test that _safe_callback handles None callback."""
        # Should not raise
        controller._safe_callback(None, "arg1", "arg2")
