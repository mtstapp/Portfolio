"""Schwab OAuth 2.0 authentication with web-based flow.

Provides two things:
  1. A Flask-based HTTPS server at https://127.0.0.1:8182 that serves a
     browser-friendly auth page AND handles the Schwab OAuth callback.
     Credentials are stored in macOS Keychain after successful auth.

  2. create_client() - builds a schwabdev.Client using Keychain credentials
     and a secure tokens file (auto-refreshes access tokens via schwabdev).

Usage:
    portfolio auth        -> starts auth server and opens browser
    portfolio auth --open -> opens auth page without starting server (if running)

The Flask server:
    GET  /          -> login page with "Authenticate with Schwab" button
    GET  /?code=... -> OAuth callback; exchanges code for tokens, saves to Keychain
    GET  /status    -> JSON { authenticated: bool, days_until_expiry: int }
"""

import json
import logging
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
import schwabdev
from flask import Flask, jsonify, redirect, render_template_string, request
from requests.auth import HTTPBasicAuth

from portfolio import config
from portfolio.auth import keychain

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_AUTH_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Portfolio Dashboard – Schwab Login</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f5f7fa; display: flex; align-items: center;
           justify-content: center; height: 100vh; margin: 0; }
    .card { background: white; border-radius: 12px; padding: 48px;
            box-shadow: 0 4px 24px rgba(0,0,0,.1); max-width: 420px; width: 100%;
            text-align: center; }
    h1 { color: #1a1a2e; font-size: 24px; margin-bottom: 8px; }
    p  { color: #666; margin-bottom: 32px; }
    a.btn { display: inline-block; background: #00a3e0; color: white;
            padding: 14px 32px; border-radius: 8px; text-decoration: none;
            font-weight: 600; font-size: 16px; transition: background .2s; }
    a.btn:hover { background: #0082b3; }
    .note { font-size: 12px; color: #999; margin-top: 24px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Portfolio Dashboard</h1>
    <p>Sign in to your Charles Schwab account to authorize access to your portfolio data.</p>
    <a class="btn" href="{{ auth_url }}">Login with Schwab</a>
    <p class="note">You will be redirected to Schwab's secure login page.<br>
       This app only requests read-only access.</p>
  </div>
</body>
</html>
"""

_SUCCESS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Authenticated – Portfolio Dashboard</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #f5f7fa;
           display: flex; align-items: center; justify-content: center;
           height: 100vh; margin: 0; }
    .card { background: white; border-radius: 12px; padding: 48px;
            box-shadow: 0 4px 24px rgba(0,0,0,.1); max-width: 420px;
            text-align: center; }
    h1 { color: #00a86b; }
    p  { color: #666; }
  </style>
  <script>setTimeout(() => window.close(), 4000);</script>
</head>
<body>
  <div class="card">
    <h1>✓ Authenticated</h1>
    <p>Your Schwab account has been connected successfully.<br>
       You can close this tab and return to the dashboard.</p>
  </div>
</body>
</html>
"""

_ERROR_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Auth Error</title></head>
<body style="font-family:sans-serif;padding:48px;text-align:center">
  <h1 style="color:#d9534f">Authentication Failed</h1>
  <p>{{ error }}</p>
  <a href="/">Try again</a>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _build_auth_url() -> str:
    app_key = keychain.require("schwab-api-key")
    callback_url = keychain.get("schwab-callback-url") or config.SCHWAB_DEFAULT_CALLBACK
    params = urlencode({
        "response_type": "code",
        "client_id": app_key,
        "redirect_uri": callback_url,
    })
    return f"{config.SCHWAB_AUTH_URL}?{params}"


def _exchange_code(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    app_key = keychain.require("schwab-api-key")
    app_secret = keychain.require("schwab-app-secret")
    callback_url = keychain.get("schwab-callback-url") or config.SCHWAB_DEFAULT_CALLBACK

    resp = requests.post(
        config.SCHWAB_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url,
        },
        auth=HTTPBasicAuth(app_key, app_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(tokens: dict) -> dict:
    """Use the refresh token to get a new access token."""
    app_key = keychain.require("schwab-api-key")
    app_secret = keychain.require("schwab-app-secret")

    resp = requests.post(
        config.SCHWAB_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        auth=HTTPBasicAuth(app_key, app_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _save_tokens(tokens: dict) -> None:
    """Persist tokens to secure SQLite DB (schwabdev-compatible schema)."""
    config.SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    now_str = datetime.now(timezone.utc).isoformat()

    con = sqlite3.connect(str(config.TOKENS_FILE))
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS schwabdev (
                access_token_issued  TEXT,
                refresh_token_issued TEXT,
                access_token         TEXT,
                refresh_token        TEXT,
                id_token             TEXT,
                expires_in           INTEGER,
                token_type           TEXT,
                scope                TEXT
            )
        """)
        con.execute("DELETE FROM schwabdev")   # keep exactly one row
        con.execute(
            "INSERT INTO schwabdev VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now_str,
                now_str,
                tokens.get("access_token", ""),
                tokens.get("refresh_token", ""),
                tokens.get("id_token", ""),
                tokens.get("expires_in", 1800),
                tokens.get("token_type", "Bearer"),
                tokens.get("scope", ""),
            ),
        )
        con.commit()
    finally:
        con.close()

    config.TOKENS_FILE.chmod(0o600)
    keychain.set("schwab-token-created-at", now_str)
    log.info("Tokens saved to %s", config.TOKENS_FILE)


def load_tokens() -> dict | None:
    """Load tokens from the secure SQLite DB. Returns None if not found."""
    if not config.TOKENS_FILE.exists():
        return None
    try:
        con = sqlite3.connect(str(config.TOKENS_FILE))
        con.row_factory = sqlite3.Row
        try:
            row = con.execute("SELECT * FROM schwabdev LIMIT 1").fetchone()
            return dict(row) if row else None
        finally:
            con.close()
    except sqlite3.Error:
        return None


def _maybe_migrate_tokens() -> None:
    """Migrate old JSON tokens (.schwab_tokens.json) to new SQLite format (.db).

    Called once from create_client() — silently does nothing if there is nothing
    to migrate (SQLite DB already exists or no old JSON file is present).
    """
    if config.TOKENS_FILE.exists():
        return  # SQLite DB already present; nothing to do
    json_file = config.SECRETS_DIR / ".schwab_tokens.json"
    if not json_file.exists():
        return  # No old file either
    try:
        tokens = json.loads(json_file.read_text())
        _save_tokens(tokens)
        json_file.rename(json_file.with_suffix(".bak"))
        log.info("Migrated Schwab tokens from JSON to SQLite format")
    except Exception as exc:
        log.warning("Failed to migrate JSON tokens to SQLite: %s", exc)


def token_days_remaining() -> float | None:
    """Return days until the 7-day refresh token expires, or None if unknown."""
    created_at_str = keychain.get("schwab-token-created-at")
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(created_at_str)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        return max(0.0, 7.0 - elapsed / 86400)
    except ValueError:
        return None


def is_authenticated() -> bool:
    """Return True if a valid tokens file exists."""
    days = token_days_remaining()
    return days is not None and days > 0


# ---------------------------------------------------------------------------
# Flask OAuth server
# ---------------------------------------------------------------------------

_auth_event = threading.Event()
_flask_app = Flask(__name__)
_flask_app.secret_key = "portfolio-oauth"  # only used for Flask internals


@_flask_app.route("/")
def index():
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return render_template_string(_ERROR_PAGE, error=error), 400

    if code:
        try:
            tokens = _exchange_code(code)
            _save_tokens(tokens)
            _auth_event.set()
            return render_template_string(_SUCCESS_PAGE)
        except Exception as exc:
            log.exception("Token exchange failed")
            return render_template_string(_ERROR_PAGE, error=str(exc)), 500

    auth_url = _build_auth_url()
    return render_template_string(_AUTH_PAGE, auth_url=auth_url)


@_flask_app.route("/status")
def status():
    days = token_days_remaining()
    return jsonify({
        "authenticated": is_authenticated(),
        "days_until_expiry": round(days, 1) if days is not None else None,
    })


def start_auth_server(open_browser: bool = True) -> None:
    """Start the HTTPS OAuth server and optionally open a browser tab.

    The server runs on https://127.0.0.1:8182 (matching the Schwab registered
    callback URL). Uses werkzeug's adhoc SSL cert – the browser will show a
    security warning for localhost which the user can dismiss.
    """
    _auth_event.clear()

    url = f"https://{config.OAUTH_SERVER_HOST}:{config.OAUTH_SERVER_PORT}"

    def _run():
        import logging as _log
        _log.getLogger("werkzeug").setLevel(_log.WARNING)
        _flask_app.run(
            host=config.OAUTH_SERVER_HOST,
            port=config.OAUTH_SERVER_PORT,
            ssl_context="adhoc",
            debug=False,
            use_reloader=False,
        )

    server_thread = threading.Thread(target=_run, daemon=True)
    server_thread.start()
    time.sleep(1.0)  # let the server start

    if open_browser:
        print(f"\nOpening auth page: {url}")
        print("If your browser shows a security warning, click 'Advanced' → 'Proceed'")
        webbrowser.open(url)

    print("Waiting for Schwab authentication... (press Ctrl+C to cancel)")
    _auth_event.wait()
    print("Authentication successful!")


# ---------------------------------------------------------------------------
# Schwab API client factory
# ---------------------------------------------------------------------------

def create_client() -> schwabdev.Client:
    """Create an authenticated schwabdev.Client.

    Loads tokens from the secure SQLite DB (~/.portfolio/.schwab_tokens.db).
    schwabdev auto-refreshes the access token (30-min expiry) and writes
    the updated token back to the database.
    """
    if not keychain.is_configured():
        raise RuntimeError(
            "Schwab credentials not in Keychain.\n"
            "Run: portfolio setup"
        )

    # Transparently migrate old JSON tokens to SQLite on first run after upgrade
    _maybe_migrate_tokens()

    if not config.TOKENS_FILE.exists():
        raise RuntimeError(
            "Not authenticated with Schwab.\n"
            "Run: portfolio auth"
        )

    days = token_days_remaining()
    if days is not None and days < 1:
        raise RuntimeError(
            "Schwab refresh token has expired (7-day limit).\n"
            "Run: portfolio auth  to re-authenticate."
        )
    if days is not None and days < 2:
        log.warning("Schwab token expires in %.1f days – re-authenticate soon!", days)

    app_key = keychain.require("schwab-api-key")
    app_secret = keychain.require("schwab-app-secret")
    callback_url = keychain.get("schwab-callback-url") or config.SCHWAB_DEFAULT_CALLBACK

    return schwabdev.Client(
        app_key,
        app_secret,
        callback_url,
        tokens_db=str(config.TOKENS_FILE),
    )
