# Unattended weekly sweep. Requires a complete profile.md; never auto-applies.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$log = "logs/sweep_$stamp.log"

if (-not (Test-Path "profile.md")) {
  "no profile.md - run /intake first; skipping sweep" | Tee-Object -FilePath $log -Append
} else {
  claude -p "/sweep" --model sonnet --permission-mode acceptEdits `
    --allowedTools "WebSearch,WebFetch,Read,Write,Edit,Bash" *>> $log
}
python tools/build_ics.py        *>> $log
python tools/build_dashboard.py  *>> $log
"done $stamp" | Out-File -FilePath $log -Append -Encoding utf8
