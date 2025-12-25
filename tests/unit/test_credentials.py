"""Tests for credential storage."""

from unittest.mock import MagicMock, patch

from tlh_agent.credentials import (
    SERVICE_NAME,
    delete_alpaca_credentials,
    get_alpaca_credentials,
    has_alpaca_credentials,
    set_alpaca_credentials,
)


class TestCredentials:
    """Tests for credential storage functions."""

    @patch("tlh_agent.credentials.keyring")
    def test_get_alpaca_credentials_found(self, mock_keyring: MagicMock) -> None:
        """Test getting credentials when they exist."""
        mock_keyring.get_password.side_effect = lambda svc, key: {
            ("tlh-agent", "alpaca_api_key"): "test-key",
            ("tlh-agent", "alpaca_secret_key"): "test-secret",
        }.get((svc, key))

        result = get_alpaca_credentials()

        assert result == ("test-key", "test-secret")

    @patch("tlh_agent.credentials.keyring")
    def test_get_alpaca_credentials_not_found(self, mock_keyring: MagicMock) -> None:
        """Test getting credentials when they don't exist."""
        mock_keyring.get_password.return_value = None

        result = get_alpaca_credentials()

        assert result is None

    @patch("tlh_agent.credentials.keyring")
    def test_get_alpaca_credentials_partial(self, mock_keyring: MagicMock) -> None:
        """Test getting credentials when only one exists."""
        mock_keyring.get_password.side_effect = lambda svc, key: {
            ("tlh-agent", "alpaca_api_key"): "test-key",
            ("tlh-agent", "alpaca_secret_key"): None,
        }.get((svc, key))

        result = get_alpaca_credentials()

        assert result is None

    @patch("tlh_agent.credentials.keyring")
    def test_set_alpaca_credentials(self, mock_keyring: MagicMock) -> None:
        """Test setting credentials."""
        set_alpaca_credentials("my-key", "my-secret")

        assert mock_keyring.set_password.call_count == 2
        mock_keyring.set_password.assert_any_call(SERVICE_NAME, "alpaca_api_key", "my-key")
        mock_keyring.set_password.assert_any_call(SERVICE_NAME, "alpaca_secret_key", "my-secret")

    @patch("tlh_agent.credentials.keyring")
    def test_delete_alpaca_credentials(self, mock_keyring: MagicMock) -> None:
        """Test deleting credentials."""
        delete_alpaca_credentials()

        assert mock_keyring.delete_password.call_count == 2
        mock_keyring.delete_password.assert_any_call(SERVICE_NAME, "alpaca_api_key")
        mock_keyring.delete_password.assert_any_call(SERVICE_NAME, "alpaca_secret_key")

    @patch("tlh_agent.credentials.keyring")
    def test_delete_alpaca_credentials_not_found(self, mock_keyring: MagicMock) -> None:
        """Test deleting credentials when they don't exist."""
        # Mock the errors module at the module level since we import it directly
        import keyring.errors

        from tlh_agent import credentials

        original_errors = credentials.keyring.errors
        mock_keyring.errors = keyring.errors
        mock_keyring.delete_password.side_effect = keyring.errors.PasswordDeleteError()

        # Should not raise
        delete_alpaca_credentials()

        credentials.keyring.errors = original_errors

    @patch("tlh_agent.credentials.keyring")
    def test_has_alpaca_credentials_true(self, mock_keyring: MagicMock) -> None:
        """Test has_alpaca_credentials when credentials exist."""
        mock_keyring.get_password.side_effect = lambda svc, key: {
            ("tlh-agent", "alpaca_api_key"): "test-key",
            ("tlh-agent", "alpaca_secret_key"): "test-secret",
        }.get((svc, key))

        assert has_alpaca_credentials() is True

    @patch("tlh_agent.credentials.keyring")
    def test_has_alpaca_credentials_false(self, mock_keyring: MagicMock) -> None:
        """Test has_alpaca_credentials when credentials don't exist."""
        mock_keyring.get_password.return_value = None

        assert has_alpaca_credentials() is False
