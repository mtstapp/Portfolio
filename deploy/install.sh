#!/bin/bash
# Install Portfolio Dashboard on Mac Mini.
# Run once after copying the repo to the Mac Mini.
#
# Usage: bash deploy/install.sh

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Installing Portfolio Dashboard from: $REPO_DIR"

# Create data directories
mkdir -p ~/data/portfolio/logs
mkdir -p ~/.portfolio
chmod 700 ~/.portfolio

# Create virtual environment and install
cd "$REPO_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
echo "✓ Python environment installed"

# Install launchd agents
AGENTS_DIR=~/Library/LaunchAgents
cp deploy/com.portfolio.refresh.plist   "$AGENTS_DIR/"
cp deploy/com.portfolio.dashboard.plist "$AGENTS_DIR/"

launchctl unload "$AGENTS_DIR/com.portfolio.refresh.plist"   2>/dev/null || true
launchctl unload "$AGENTS_DIR/com.portfolio.dashboard.plist" 2>/dev/null || true

launchctl load -w "$AGENTS_DIR/com.portfolio.refresh.plist"
launchctl load -w "$AGENTS_DIR/com.portfolio.dashboard.plist"

echo "✓ launchd agents installed"
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Run: .venv/bin/portfolio setup   (store Schwab credentials in Keychain)"
echo "  2. Run: .venv/bin/portfolio auth    (authenticate with Schwab)"
echo "  3. Run: .venv/bin/portfolio refresh (pull initial data)"
echo ""
MAC=$(hostname -s).local
echo "Dashboard will be available at: http://$MAC:8501"
