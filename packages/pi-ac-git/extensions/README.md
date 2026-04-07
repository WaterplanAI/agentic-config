# extensions

This directory exports package-local pi extensions for `@agentic-config/pi-ac-git`.

Current shipped surface:
- `hook-compat.js` — registers the bundled `git-commit-guard.py` script with the shared `@agentic-config/pi-compat` hook adapter using the package `assets/` directory as the packaged plugin root.
