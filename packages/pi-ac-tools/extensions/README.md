# extensions

This directory exports package-local pi extensions for `@agentic-config/pi-ac-tools`.

Current shipped surface:
- `hook-compat.js` — registers the bundled `dry-run-guard.py` and `gsuite-public-asset-guard.py` scripts with the shared `@agentic-config/pi-compat` hook adapter using the package `assets/` directory as the packaged plugin root.
