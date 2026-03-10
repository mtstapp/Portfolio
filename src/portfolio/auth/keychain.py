"""macOS Keychain integration via the keyring library.

All application secrets are stored under the service name 'portfolio-dashboard'.
Never store credentials in files, environment variables, or source code.

Keys used:
    schwab-api-key          Schwab client ID (app key)
    schwab-app-secret       Schwab client secret
    schwab-callback-url     OAuth callback URL
    schwab-token-created-at ISO timestamp when the refresh token was issued
    perplexity-api-key      Perplexity AI API key
    google-sheets-creds     Path to Google service account JSON file
    plaid-client-id         (Phase 2) Plaid client ID
    plaid-secret            (Phase 2) Plaid secret
    plaid-access-token-ml   (Phase 2) ML Benefits Plaid access token
"""

import keyring
import keyring.errors

SERVICE = "portfolio-dashboard"


def get(key: str) -> str | None:
    """Read a secret from the macOS Keychain. Returns None if not found."""
    return keyring.get_password(SERVICE, key)


def set(key: str, value: str) -> None:
    """Write a secret to the macOS Keychain."""
    keyring.set_password(SERVICE, key, value)


def delete(key: str) -> None:
    """Delete a secret from the macOS Keychain. Silent if not found."""
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass


def require(key: str) -> str:
    """Read a secret, raising RuntimeError if it is not set."""
    value = get(key)
    if not value:
        raise RuntimeError(
            f"Required credential '{key}' not found in Keychain.\n"
            f"Run: portfolio setup"
        )
    return value


def is_configured() -> bool:
    """Return True if the minimum required Schwab credentials are stored."""
    return bool(get("schwab-api-key") and get("schwab-app-secret"))
