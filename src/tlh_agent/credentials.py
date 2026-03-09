"""Secure credential storage using macOS Keychain.

This module provides secure storage for API credentials using the system keychain.
On macOS, this uses the native Keychain. On other platforms, it falls back to
the platform's secure credential storage.
"""

import contextlib

import keyring
import keyring.errors

SERVICE_NAME = "tlh-agent"


def _alpaca_keychain_keys(paper: bool) -> tuple[str, str]:
    """Get keychain keys for the given trading mode.

    Args:
        paper: Whether to use paper trading keys.

    Returns:
        Tuple of (api_key_name, secret_key_name) for keychain lookup.
    """
    suffix = "_paper" if paper else "_live"
    return (f"alpaca_api_key{suffix}", f"alpaca_secret_key{suffix}")


def get_alpaca_credentials(paper: bool = True) -> tuple[str, str] | None:
    """Get Alpaca API credentials from the keychain.

    Looks up mode-specific keys first (e.g. alpaca_api_key_paper),
    then falls back to legacy unqualified keys for backwards compatibility.

    Args:
        paper: Whether to get paper trading credentials (default True).

    Returns:
        Tuple of (api_key, secret_key) if found, None otherwise.
    """
    api_name, secret_name = _alpaca_keychain_keys(paper)
    api_key = keyring.get_password(SERVICE_NAME, api_name)
    secret_key = keyring.get_password(SERVICE_NAME, secret_name)

    if api_key and secret_key:
        return (api_key, secret_key)

    # Fall back to legacy unqualified keys
    api_key = keyring.get_password(SERVICE_NAME, "alpaca_api_key")
    secret_key = keyring.get_password(SERVICE_NAME, "alpaca_secret_key")

    if api_key and secret_key:
        return (api_key, secret_key)
    return None


def set_alpaca_credentials(api_key: str, secret_key: str, paper: bool = True) -> None:
    """Store Alpaca API credentials in the keychain.

    Args:
        api_key: Alpaca API key.
        secret_key: Alpaca secret key.
        paper: Whether these are paper trading credentials (default True).
    """
    api_name, secret_name = _alpaca_keychain_keys(paper)
    keyring.set_password(SERVICE_NAME, api_name, api_key)
    keyring.set_password(SERVICE_NAME, secret_name, secret_key)


def delete_alpaca_credentials(paper: bool = True) -> None:
    """Remove Alpaca API credentials from the keychain.

    Args:
        paper: Whether to delete paper trading credentials (default True).
    """
    api_name, secret_name = _alpaca_keychain_keys(paper)
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, api_name)

    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, secret_name)


def has_alpaca_credentials(paper: bool = True) -> bool:
    """Check if Alpaca credentials exist in the keychain.

    Args:
        paper: Whether to check paper trading credentials (default True).

    Returns:
        True if both api_key and secret_key are stored.
    """
    return get_alpaca_credentials(paper) is not None


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
