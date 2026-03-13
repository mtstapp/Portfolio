"""One-time CLI to store credentials in macOS Keychain.

Run once on each machine (dev laptop and Mac Mini):
    portfolio setup

Prompts for each credential with getpass (no echo). Optionally migrates
existing credentials from an .env file.

Flags:
    --show    Visible input (no masking) so you can verify what you paste
    --verify  Print currently stored values (partially masked), no prompts
"""

import getpass
from pathlib import Path

from portfolio.auth import keychain


def _mask(value: str) -> str:
    """Return a partially-masked string for verification output.

    Shows first 6 and last 4 characters with '...' in between so the user
    can compare against what's shown in the Schwab Developer Portal without
    exposing the full secret.

    If the value is suspiciously short (≤10 chars) it is shown in full
    with a warning, since that likely indicates a truncation error.
    """
    if not value:
        return "(empty)"
    if len(value) <= 10:
        return f"{value}  ⚠ very short (expected 32+ chars)"
    return f"{value[:6]}...{value[-4:]}  ({len(value)} chars)"


def run_setup(
    migrate_env: str | None = None,
    show: bool = False,
    verify: bool = False,
) -> None:
    """Interactive credential setup. Stores all secrets in Keychain.

    Args:
        migrate_env: Path to .env file to migrate credentials from.
        show: Use visible input (no masking) for easier paste verification.
        verify: Print currently stored values (partially masked); no prompts.
    """
    from portfolio.auth.keychain import KEYCHAIN_FILE

    print("\n=== Portfolio Dashboard – Credentials Setup ===\n")
    print(f"Storing credentials in: {KEYCHAIN_FILE}\n")

    if verify:
        _show_current_values()
        return

    # Always start with a fresh keychain to avoid macOS password dialog issues.
    # This deletes and recreates with a known password so unlock never blocks.
    keychain.reset()

    if show:
        print("ℹ  Visible input mode (--show): keystrokes will be visible.\n")

    existing_env: dict[str, str] = {}
    if migrate_env:
        env_path = Path(migrate_env)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing_env[k.strip()] = v.strip().strip('"').strip("'")
            print(f"Found existing credentials in {migrate_env}\n")

    def _prompt(label: str, env_key: str | None = None, keychain_key: str | None = None,
                secret: bool = True) -> str:
        existing = ""
        if env_key and env_key in existing_env:
            existing = existing_env[env_key]
        if keychain_key:
            stored = keychain.get(keychain_key)
            if stored:
                existing = stored

        if existing:
            hint = f" [{_mask(existing)} – Enter to keep]"
        else:
            hint = ""

        prompt_str = f"{label}{hint}: "
        if secret and not show:
            value = getpass.getpass(prompt_str) or existing
        else:
            value = input(prompt_str) or existing

        return value.strip()

    # ── Schwab credentials ────────────────────────────────────────────────
    print("── Schwab API Credentials ──────────────────────────")
    print("Get these from https://developer.schwab.com → My Apps → your app\n")

    app_key = _prompt("Schwab App Key (Client ID)", "app_key", "schwab-api-key")
    app_secret = _prompt("Schwab App Secret", "app_secret", "schwab-app-secret")
    callback_url = _prompt(
        "Callback URL",
        "callback_url",
        "schwab-callback-url",
        secret=False,
    ) or "https://127.0.0.1:8182"

    if app_key:
        keychain.set("schwab-api-key", app_key)
        print(f"  ✓ App Key stored:    {_mask(app_key)}")
    if app_secret:
        keychain.set("schwab-app-secret", app_secret)
        print(f"  ✓ App Secret stored: {_mask(app_secret)}")
    keychain.set("schwab-callback-url", callback_url)
    print(f"  ✓ Callback URL:      {callback_url}\n")

    # ── Perplexity (optional) ─────────────────────────────────────────────
    print("── Perplexity AI (optional) ────────────────────────")
    print("Used for AI-assisted stock classification. Leave blank to skip.\n")

    perplexity_key = _prompt(
        "Perplexity API Key (leave blank to skip)",
        "PERPLEXITY_API_KEY",
        "perplexity-api-key",
    )
    if perplexity_key:
        keychain.set("perplexity-api-key", perplexity_key)
        print(f"  ✓ Perplexity key stored: {_mask(perplexity_key)}\n")
    else:
        print("  Skipping Perplexity.\n")

    # ── Google Sheets (optional) ──────────────────────────────────────────
    print("── Google Sheets Service Account (optional) ────────")
    print("Used for the Allocations sheet. Leave blank to skip.\n")

    gs_creds_path = _prompt(
        "Path to service account JSON (e.g. /Users/mark/dev/cspullFiles/CSPull438202.json)",
        keychain_key="google-sheets-creds",
        secret=False,
    )
    if gs_creds_path:
        keychain.set("google-sheets-creds", gs_creds_path)
        print(f"  ✓ Google Sheets path stored: {gs_creds_path}\n")
    else:
        print("  Skipping Google Sheets.\n")

    print("✓ Setup complete!")
    print("\nNext step: run 'portfolio auth' to authenticate with Schwab.")


def _show_current_values() -> None:
    """Print all currently stored Keychain values (partially masked)."""
    fields = [
        ("Schwab App Key",     "schwab-api-key",       True),
        ("Schwab App Secret",  "schwab-app-secret",    True),
        ("Callback URL",       "schwab-callback-url",  False),
        ("Perplexity API Key", "perplexity-api-key",   True),
        ("Google Sheets Path", "google-sheets-creds",  False),
    ]

    print("── Currently stored credentials ────────────────────\n")
    for label, key, is_secret in fields:
        value = keychain.get(key)
        if value:
            display = _mask(value) if is_secret else value
        else:
            display = "(not set)"
        print(f"  {label:<22}  {display}")

    print()
    print("To update:               portfolio setup")
    print("To re-enter visibly:     portfolio setup --show")
