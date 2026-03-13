"""macOS Keychain integration via the security CLI.

All application secrets are stored under the service name 'portfolio-dashboard'.
Never store credentials in files, environment variables, or source code.

Uses the macOS `security` CLI instead of the keyring library to avoid
errSecInteractionNotAllowed (-25308) errors in headless/launchd contexts.
Items are stored with -A (allow all applications) so no UI prompt is required
once the Keychain is unlocked.

If the Keychain is locked (after screen lock or Mac sleep), a RuntimeError is
raised with clear instructions rather than the misleading "credentials not found"
message. Fix: disable Keychain auto-lock via Keychain Access → Edit → Change
Settings for 'login' → uncheck both lock options.

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

import subprocess

SERVICE = "portfolio-dashboard"

# Substrings in security CLI stderr that indicate the Keychain is locked,
# rather than the item simply being absent.
_LOCKED_MARKERS = (
    "interaction not allowed",
    "errSecInteractionNotAllowed",
)

_UNLOCK_HINT = (
    "The macOS Keychain is locked.\n"
    "Unlock it:       security unlock-keychain ~/Library/Keychains/login.keychain-db\n"
    "Prevent locking: open Keychain Access → select 'login' → "
    "Edit → Change Settings → uncheck both auto-lock options."
)


def _is_locked_error(stderr: str) -> bool:
    """Return True if the security CLI stderr indicates a locked Keychain."""
    sl = stderr.lower()
    return any(m.lower() in sl for m in _LOCKED_MARKERS)


def get(key: str) -> str | None:
    """Read a secret from the macOS Keychain.

    Returns None if the item is not found (errSecItemNotFound / rc=44).
    Raises RuntimeError if the Keychain is locked or otherwise inaccessible,
    so callers get a clear message instead of a misleading 'credentials not found'.
    """
    result = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICE, "-a", key, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip() or None
    if _is_locked_error(result.stderr):
        raise RuntimeError(_UNLOCK_HINT)
    # rc=44 = errSecItemNotFound — item genuinely not present
    return None


def set(key: str, value: str) -> None:
    """Write a secret to the macOS Keychain, allowing all applications to read it."""
    result = subprocess.run(
        ["security", "add-generic-password", "-U", "-A", "-s", SERVICE, "-a", key, "-w", value],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if _is_locked_error(result.stderr):
            raise RuntimeError(_UNLOCK_HINT)
        raise RuntimeError(f"Failed to store keychain item '{key}': {result.stderr.strip()}")


def delete(key: str) -> None:
    """Delete a secret from the macOS Keychain. Silent if not found."""
    subprocess.run(
        ["security", "delete-generic-password", "-s", SERVICE, "-a", key],
        capture_output=True,
    )


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
    """Return True if the minimum required Schwab credentials are stored.

    Raises RuntimeError if the Keychain is locked, so the caller gets a
    clear unlock message rather than a misleading 'credentials not found'.
    """
    return bool(get("schwab-api-key") and get("schwab-app-secret"))
