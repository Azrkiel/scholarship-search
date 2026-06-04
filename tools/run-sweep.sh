#!/usr/bin/env bash
# Unattended weekly sweep. Requires a complete profile.md; never auto-applies.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
stamp=$(date +%Y-%m-%d_%H%M)
log="logs/sweep_$stamp.log"

if [ ! -f profile.md ]; then
  echo "no profile.md — run /intake first; skipping sweep" | tee -a "$log"
else
  claude -p "/sweep" --model sonnet --permission-mode acceptEdits \
    --allowedTools "WebSearch,WebFetch,Read,Write,Edit,Bash" >>"$log" 2>&1 \
    || echo "claude sweep exited non-zero; rebuilding views from existing CSV" >>"$log"
fi

python3 tools/build_ics.py       >>"$log" 2>&1 || echo "build_ics failed" >>"$log"
python3 tools/build_dashboard.py >>"$log" 2>&1 || echo "build_dashboard failed" >>"$log"
echo "done $stamp" >>"$log"
