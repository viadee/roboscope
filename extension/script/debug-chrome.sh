#!/usr/bin/env bash
# Launch Chrome with the extension loaded from source for debugging.
# Uses a persistent profile so state (storage, settings) survives restarts.
#
# Usage:
#   ./script/debug-chrome.sh [URL]
#
# The service worker console is at: chrome://extensions → "Inspect views: service worker"
# Or open chrome://inspect/#service-workers

set -euo pipefail

EXTENSION_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE_DIR="$EXTENSION_DIR/.chrome-debug-profile"
START_URL="${1:-https://example.com}"

# Detect Chrome binary
if [[ -d "/Applications/Google Chrome.app" ]]; then
  CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif command -v google-chrome &>/dev/null; then
  CHROME="google-chrome"
elif command -v chromium &>/dev/null; then
  CHROME="chromium"
else
  echo "Error: Chrome not found. Install Google Chrome or set CHROME env var." >&2
  exit 1
fi

echo "Extension dir: $EXTENSION_DIR"
echo "Profile dir:   $PROFILE_DIR"
echo "Start URL:     $START_URL"
echo ""
echo "Tips:"
echo "  - Service worker logs: chrome://extensions → click 'service worker' link"
echo "  - Content script logs: open DevTools (F12) on any page"
echo "  - Storage state:       chrome://extensions → click 'service worker' → Application tab"
echo ""

"$CHROME" \
  --user-data-dir="$PROFILE_DIR" \
  --load-extension="$EXTENSION_DIR" \
  --auto-open-devtools-for-tabs \
  --enable-logging \
  --v=1 \
  "$START_URL"
