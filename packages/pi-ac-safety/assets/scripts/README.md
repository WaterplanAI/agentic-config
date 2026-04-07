# script assets

This directory contains bundled guardian scripts used by `@agentic-config/pi-ac-safety`.

Current shipped surface:
- `hooks/_lib.py`
- `hooks/credential-guardian.py`
- `hooks/destructive-bash-guardian.py`
- `hooks/supply-chain-guardian.py`
- `hooks/write-scope-guardian.py`
- `hooks/playwright-guardian.py`

These files are executed through the shared `@agentic-config/pi-compat` hook adapter.
The Playwright guard targets the current Bash-based `playwright-cli` surface shipped in pi.
