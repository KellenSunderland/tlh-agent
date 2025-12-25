"""Secure credential storage using macOS Keychain.

This module provides secure storage for API credentials using the system keychain.
On macOS, this uses the native Keychain. On other platforms, it falls back to
the platform's secure credential storage.
"""

import contextlib

import keyring
import keyring.errors

SERVICE_NAME = "tlh-agent"


def get_alpaca_credentials() -> tuple[str, str] | None:
    """Get Alpaca API credentials from the keychain.

    Returns:
        Tuple of (api_key, secret_key) if found, None otherwise.
    """
    api_key = keyring.get_password(SERVICE_NAME, "alpaca_api_key")
    secret_key = keyring.get_password(SERVICE_NAME, "alpaca_secret_key")

    if api_key and secret_key:
        return (api_key, secret_key)
    return None


def set_alpaca_credentials(api_key: str, secret_key: str) -> None:
    """Store Alpaca API credentials in the keychain.

    Args:
        api_key: Alpaca API key.
        secret_key: Alpaca secret key.
    """
    keyring.set_password(SERVICE_NAME, "alpaca_api_key", api_key)
    keyring.set_password(SERVICE_NAME, "alpaca_secret_key", secret_key)


def delete_alpaca_credentials() -> None:
    """Remove Alpaca API credentials from the keychain."""
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, "alpaca_api_key")

    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, "alpaca_secret_key")


def has_alpaca_credentials() -> bool:
    """Check if Alpaca credentials exist in the keychain.

    Returns:
        True if both api_key and secret_key are stored.
    """
    return get_alpaca_credentials() is not None


def get_claude_api_key() -> str | None:
    """Get Claude API key from the keychain.

    Returns:
        API key if found, None otherwise.
    """
    return keyring.get_password(SERVICE_NAME, "claude_api_key")


def set_claude_api_key(api_key: str) -> None:
    """Store Claude API key in the keychain.

    Args:
        api_key: Anthropic API key.
    """
    keyring.set_password(SERVICE_NAME, "claude_api_key", api_key)


def delete_claude_api_key() -> None:
    """Remove Claude API key from the keychain."""
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, "claude_api_key")


def has_claude_api_key() -> bool:
    """Check if Claude API key exists in the keychain.

    Returns:
        True if api_key is stored.
    """
    return get_claude_api_key() is not None
