# Portfolio Dashboard – Mac Mini Installation Guide

Complete instructions to set up the portfolio dashboard on your Mac Mini for automated daily data pulls and always-on dashboard access.

## Prerequisites

Ensure you have:
- **macOS** (10.13+)
- **Python 3.11+** installed (recommended via [pyenv](https://github.com/pyenv/pyenv))
- **Git**
- **Schwab API credentials** from developer.schwab.com (client ID + secret)

Check your Python version:
```bash
python3 --version
```

## Step 1: Clone the Repository

```bash
cd ~
git clone https://github.com/mtstapp/Portfolio.git
cd Portfolio
```

## Step 2: Set Python Version (if using pyenv)

```bash
echo "3.11" > .python-version
pyenv install 3.11.10  # if not already installed
pyenv local 3.11.10
```

Verify:
```bash
python3 --version
```

## Step 3: Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e .
```

This installs the portfolio package and all dependencies.

## Step 4: Store Schwab Credentials in Keychain

```bash
.venv/bin/portfolio setup
```

You'll be prompted for:
- **Schwab App Key (Client ID)** – from developer.schwab.com
- **Schwab App Secret** – from developer.schwab.com
- **Callback URL** – default is `https://127.0.0.1:8182` (don't change unless you updated the Schwab app registration)
- **Perplexity API Key** (optional) – for AI stock summaries
- **Google Sheets credentials** (optional) – path to service account JSON for allocation overrides

All credentials are stored securely in macOS Keychain (service: `portfolio-dashboard`). Never stored in files or environment variables.

## Step 5: Authenticate with Schwab

```bash
.venv/bin/portfolio auth
```

This opens an HTTPS auth page at `https://127.0.0.1:8182`. You'll see a browser security warning (self-signed cert on localhost) – click **Advanced → Proceed anyway**.

Then:
1. Click **Login with Schwab**
2. Log in to your Schwab account
3. Grant access to the portfolio app
4. The page shows "✓ Authenticated"

OAuth tokens are saved to `~/.portfolio/.schwab_tokens.json` (outside the git repo).

## Step 6: Pull Initial Data

```bash
.venv/bin/portfolio refresh
```

This:
- Fetches all accounts and positions from Schwab
- Enriches with sector/industry data via yfinance
- Fetches fundamental data (P/E, beta, dividends, etc.)
- Writes raw and canonical Parquet files to `~/data/portfolio/`

Takes 1-2 minutes the first time (subsequent refreshes are faster).

## Step 7: Verify Dashboard Works Locally

```bash
.venv/bin/streamlit run src/portfolio/dashboard/app.py
```

Open your browser to `http://localhost:8501` and verify the overview page loads with your portfolio data.

Press `Ctrl+C` to stop (we'll run it as a service next).

## Step 8: Install launchd Services

```bash
bash deploy/install.sh
```

This:
- Creates data directories with proper permissions
- Copies launchd agent plists to `~/Library/LaunchAgents/`
- Loads both agents to start automatically at login

Verify the agents are loaded:
```bash
launchctl list | grep portfolio
```

You should see:
```
com.portfolio.dashboard
com.portfolio.refresh
```

## Step 9: Access the Dashboard

The dashboard is now running as a service. Access it from any device on your local network:

```
http://<mac-mini-hostname>.local:8501
```

Example:
```
http://mac-mini.local:8501
```

Find your Mac Mini's hostname:
```bash
hostname -s
```

## Step 10: Verify Daily Refresh

Check that the refresh runs at 4:30 PM ET (16:30 local time):

```bash
tail -f ~/data/portfolio/logs/refresh.log
```

You should see log entries at 4:30 PM with summaries like:
```
=== Refresh complete: 42 positions across 4 accounts | 127 transactions ===
```

## Troubleshooting

### Dashboard won't start
Check the logs:
```bash
tail -f ~/data/portfolio/logs/dashboard_error.log
```

If the port is already in use, kill the process:
```bash
lsof -i :8501 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

Then check the launchd agent status:
```bash
launchctl stop com.portfolio.dashboard
launchctl start com.portfolio.dashboard
```

### Refresh fails
Check the logs:
```bash
tail -f ~/data/portfolio/logs/refresh_error.log
```

Common issues:
- **Token expired**: Run `portfolio auth` again (tokens expire every 7 days)
- **Network error**: Check internet connectivity
- **yfinance rate limit**: Try again in a few minutes

### Schwab token expired
Every 7 days, you'll get a macOS notification at day 5. Re-authenticate:
```bash
.venv/bin/portfolio auth
```

## Check Status Anytime

```bash
.venv/bin/portfolio status
```

Shows:
- Whether credentials are in Keychain
- Schwab token expiry date
- Last refresh date
- Number of holdings and total portfolio value

## Scheduled Refresh Times

The daily refresh runs at **4:30 PM ET** on weekdays (skips weekends and US market holidays).

To change the time, edit:
```bash
nano ~/Library/LaunchAgents/com.portfolio.refresh.plist
```

Find the `<dict>` under `<key>StartCalendarInterval</key>` and change `<integer>16</integer>` (hour) or `<integer>30</integer>` (minute). Then reload:

```bash
launchctl unload ~/Library/LaunchAgents/com.portfolio.refresh.plist
launchctl load -w ~/Library/LaunchAgents/com.portfolio.refresh.plist
```

## Uninstall

To remove the services:
```bash
launchctl unload ~/Library/LaunchAgents/com.portfolio.refresh.plist
launchctl unload ~/Library/LaunchAgents/com.portfolio.dashboard.plist
rm ~/Library/LaunchAgents/com.portfolio.*
```

Data files remain at `~/data/portfolio/` for backup.

## Support

For issues, check:
1. Dashboard logs: `~/data/portfolio/logs/dashboard*.log`
2. Refresh logs: `~/data/portfolio/logs/refresh*.log`
3. Keychain: `security find-generic-password -s portfolio-dashboard -a <key>`
4. Token file: `~/.portfolio/.schwab_tokens.json` (exists and readable)

---

**Next steps after installation:**

Once the dashboard is running, you can set up additional features:
- **Google Sheets allocation overrides** (Phase 2) – manual asset class and risk scoring
- **Merrill Lynch Benefits** (Phase 2) – CSV import or Plaid integration
- **Performance, Income, Risk dashboards** (Phases 3-4)
