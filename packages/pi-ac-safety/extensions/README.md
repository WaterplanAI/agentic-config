# extensions

This directory exports package-local pi extensions for `@agentic-config/pi-ac-safety`.

Current shipped surface:
- `hook-compat.js` — registers the bundled safety guardian scripts with the shared `@agentic-config/pi-compat` hook adapter using the package `assets/` directory as the packaged plugin root, including the current `playwright-cli` Bash guard surface.
