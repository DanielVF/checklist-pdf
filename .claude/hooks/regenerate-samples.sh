#!/usr/bin/env bash
set -euo pipefail

# Read hook JSON from stdin and extract the edited file path
INPUT=$(</dev/stdin)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only regenerate if a .py or .md file was edited
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.(py|md)$ ]]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Regenerate PDF
uv run checklistpdf.py samples/sample_fire_response.md samples/sample_fire_response.pdf

# Regenerate screenshot (page 1, top 45%, 200 DPI)
TMPIMG=$(mktemp /tmp/page1_XXXXXX.png)
pdftoppm -png -r 200 -f 1 -l 1 samples/sample_fire_response.pdf "${TMPIMG%.png}"
# pdftoppm appends -1.png to the prefix
TMPIMG="${TMPIMG%.png}-1.png"

uv run python -c "
from PIL import Image
img = Image.open('$TMPIMG')
w, h = img.size
img.crop((0, 0, w, int(h * 0.45))).save('samples/sample_screenshot.png')
"

rm -f "$TMPIMG"
