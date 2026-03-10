"""One-time CLI to store credentials in macOS Keychain.

Run once on each machine (dev laptop and Mac Mini):
    portfolio setup

Prompts for each credential with getpass (no echo). Optionally migrates
existing credentials from an .env file.
"""

import getpass
from pathlib import Path

from portfolio.auth import keychain


def run_setup(migrate_env: str | None = None) -> None:
    """Interactive credential setup. Stores all secrets in Keychain."""

    print("\n=== Portfolio Dashboard – Credentials Setup ===\n")

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
            hint = f" [{'*' * min(8, len(existing))} – press Enter to keep]"
        else:
            hint = ""

        prompt_str = f"{label}{hint}: "
        if secret:
            value = getpass.getpass(prompt_str) or existing
        else:
            value = input(prompt_str) or existing

        return value.strip()

    # Schwab credentials
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
    if app_secret:
        keychain.set("schwab-app-secret", app_secret)
    keychain.set("schwab-callback-url", callback_url)
    print("✓ Schwab credentials stored in Keychain\n")

    # Perplexity (optional)
    print("── Perplexity AI (optional) ────────────────────────")
    print("Used for AI-powered stock news summaries. Leave blank to skip.\n")

    perplexity_key = _prompt(
        "Perplexity API Key (leave blank to skip)",
        "PERPLEXITY_API_KEY",
        "perplexity-api-key",
    )
    if perplexity_key:
        keychain.set("perplexity-api-key", perplexity_key)
        print("✓ Perplexity key stored in Keychain\n")
    else:
        print("Skipping Perplexity.\n")

    # Google Sheets (optional)
    print("── Google Sheets Service Account (optional) ────────")
    print("Used for the Allocations sheet. Leave blank to skip.\n")

    gs_creds_path = _prompt(
        "Path to service account JSON (e.g. /Users/mark/dev/cspullFiles/CSPull438202.json)",
        keychain_key="google-sheets-creds",
        secret=False,
    )
    if gs_creds_path:
        keychain.set("google-sheets-creds", gs_creds_path)
        print("✓ Google Sheets credentials path stored in Keychain\n")
    else:
        print("Skipping Google Sheets.\n")

    print("✓ Setup complete!")
    print("\nNext step: run 'portfolio auth' to authenticate with Schwab.")
