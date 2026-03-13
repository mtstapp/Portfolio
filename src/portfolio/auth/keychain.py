"""macOS Keychain integration via the security CLI.

All application secrets are stored in a dedicated per-app Keychain at:
    ~/Library/Keychains/portfolio.keychain-db

Using a separate file (rather than the login Keychain) means credentials
are accessible in headless SSH and launchd contexts without auto-lock
problems or user-interaction prompts.

The Keychain is created automatically on first ``portfolio setup`` with:
  - A known app-level password (avoids empty-string edge cases)
  - Auto-lock disabled  (-t 0, no lock on sleep)

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
from pathlib import Path

SERVICE = "portfolio-dashboard"

# Dedicated per-app Keychain — never auto-locks, known password for
# non-interactive unlock.  Kept separate from login.keychain which is
# unavailable/locked in headless SSH sessions and launchd contexts.
KEYCHAIN_FILE = Path.home() / "Library" / "Keychains" / "portfolio.keychain-db"

# Known password for the portfolio Keychain.  Using a non-empty string
# avoids macOS edge-cases where an empty password triggers GUI prompts
# on some versions.  The file is user-owned (600 perms) on a single-user
# Mac Mini, so this is not a meaningful security trade-off.
_KEYCHAIN_PASSWORD = "portfolio-dashboard"

# Substrings in security CLI stderr that indicate the Keychain is locked
# rather than the item simply being absent.
_LOCKED_MARKERS = (
    "interaction not allowed",
    "errSecInteractionNotAllowed",
)

_UNLOCK_HINT = (
    f"The portfolio Keychain is locked or inaccessible ({KEYCHAIN_FILE}).\n"
    f"Unlock: security unlock-keychain -p portfolio-dashboard {KEYCHAIN_FILE}\n"
    f"Or recreate: portfolio setup"
)


def _is_locked_error(stderr: str) -> bool:
    """Return True if the security CLI error indicates a locked Keychain."""
    sl = stderr.lower()
    return any(m.lower() in sl for m in _LOCKED_MARKERS)


def _unlock_keychain() -> bool:
    """Unlock the portfolio Keychain using its known password (non-interactive).

    Returns True on success, False on failure.  A 5-second timeout prevents
    the subprocess from blocking indefinitely if macOS shows a GUI password
    dialog (which bypasses capture_output).
    """
    try:
        result = subprocess.run(
            ["security", "unlock-keychain", "-p", _KEYCHAIN_PASSWORD,
             str(KEYCHAIN_FILE)],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _delete_keychain() -> None:
    """Properly remove the portfolio Keychain file AND its search-list entry.

    ``security delete-keychain`` does both in one step, unlike a bare
    ``Path.unlink()`` which leaves a dangling reference that can trigger
    macOS password dialogs.
    """
    subprocess.run(
        ["security", "delete-keychain", str(KEYCHAIN_FILE)],
        capture_output=True,
    )
    # Belt-and-suspenders: if the file somehow survived, remove it.
    if KEYCHAIN_FILE.exists():
        KEYCHAIN_FILE.unlink()


def _create_keychain() -> None:
    """Create a fresh portfolio Keychain with the known password and no auto-lock.

    IMPORTANT: ``security create-keychain`` *replaces* the user's keychain
    search list with only the new keychain — removing login.keychain and
    any others.  We save the existing list first and restore it afterwards
    (with our keychain prepended) so nothing else breaks.
    """
    # ── 1. Save the current search list ──────────────────────────────────
    existing = subprocess.run(
        ["security", "list-keychains", "-d", "user"],
        capture_output=True, text=True,
    )
    prev_keychains = [
        line.strip().strip('"')
        for line in existing.stdout.splitlines()
        if line.strip()
    ]

    # ── 2. Create the keychain ───────────────────────────────────────────
    result = subprocess.run(
        ["security", "create-keychain", "-p", _KEYCHAIN_PASSWORD,
         str(KEYCHAIN_FILE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create portfolio Keychain at {KEYCHAIN_FILE}:\n"
            f"{result.stderr.strip()}"
        )

    # ── 3. Restore search list with our keychain prepended ───────────────
    all_keychains = [str(KEYCHAIN_FILE)] + [
        k for k in prev_keychains if k != str(KEYCHAIN_FILE)
    ]
    subprocess.run(
        ["security", "list-keychains", "-d", "user", "-s"] + all_keychains,
        capture_output=True,
    )

    # ── 4. Disable auto-lock and unlock ──────────────────────────────────
    # -t 0 = no auto-lock timeout; omitting -l = don't lock on sleep
    subprocess.run(
        ["security", "set-keychain-settings", "-t", "0", str(KEYCHAIN_FILE)],
        capture_output=True,
    )
    # Newly-created Keychains start locked — unlock immediately.
    _unlock_keychain()


def _ensure_keychain() -> None:
    """Ensure the portfolio Keychain exists and is unlocked.

    If the Keychain file exists but cannot be unlocked with the known password
    (e.g. created by an older version of the code, or the file is corrupted),
    it is deleted and recreated so the user never sees a macOS password dialog.
    Any previously stored credentials will need to be re-entered via
    ``portfolio setup``.
    """
    if KEYCHAIN_FILE.exists():
        if _unlock_keychain():
            return  # Exists and successfully unlocked — done.
        # Unlock failed (wrong password, dialog timeout, or corrupted file).
        # Properly delete (removes from search list too) and recreate.
        _delete_keychain()

    _create_keychain()


def reset() -> None:
    """Delete and recreate the portfolio Keychain with a fresh known password.

    Called at the start of ``portfolio setup`` to guarantee a clean state
    and prevent any macOS password dialogs from a stale Keychain file.
    Uses ``security delete-keychain`` so the old entry is also removed from
    the macOS keychain search list.
    """
    _delete_keychain()
    _create_keychain()


def get(key: str) -> str | None:
    """Read a secret from the portfolio Keychain.

    Returns None if the item is not found or the Keychain doesn't exist.
    Unlocks proactively before reading; if unlock fails, returns None rather
    than proceeding (which could trigger a macOS password dialog).
    """
    if not KEYCHAIN_FILE.exists():
        return None
    if not _unlock_keychain():
        # Can't unlock (wrong password or corrupted) — treat as not configured.
        # The user should run 'portfolio setup' to recreate the Keychain.
        return None
    result = subprocess.run(
        ["security", "find-generic-password",
         "-s", SERVICE, "-a", key, "-w", str(KEYCHAIN_FILE)],
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
    """Write a secret to the portfolio Keychain.

    Creates the Keychain on first use if it doesn't exist yet.
    _ensure_keychain() guarantees the Keychain is unlocked before the write,
    so no macOS password dialog will appear.
    """
    _ensure_keychain()
    result = subprocess.run(
        ["security", "add-generic-password",
         "-U", "-A", "-s", SERVICE, "-a", key, "-w", value, str(KEYCHAIN_FILE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to store keychain item '{key}': {result.stderr.strip()}")


def delete(key: str) -> None:
    """Delete a secret from the portfolio Keychain. Silent if not found."""
    subprocess.run(
        ["security", "delete-generic-password",
         "-s", SERVICE, "-a", key, str(KEYCHAIN_FILE)],
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

    Raises RuntimeError if the Keychain is locked or inaccessible, so callers
    get a clear message rather than a misleading 'credentials not found'.
    """
    return bool(get("schwab-api-key") and get("schwab-app-secret"))
