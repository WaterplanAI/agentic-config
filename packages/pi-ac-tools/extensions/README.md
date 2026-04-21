# extensions

This directory exports package-local pi extensions for `@agentic-config/pi-ac-tools`.

Current shipped surface:
- `hook-compat.js` — registers the bundled `dry-run-guard.py` and `gsuite-public-asset-guard.py` scripts with the shared `@agentic-config/pi-compat` hook adapter using the package `assets/` directory as the packaged plugin root.
- `say.ts`
  - package-local import of the user `say` voice-alert extension runtime
  - exports the `say` tool plus `/voice-status`, `/voice-auto`, `/voice-voice`, `/voice-pick`, `/voice-rate`, `/voice-threshold`, `/voice-voices`, and `/voice-preview`
- `web-search/`
  - `index.ts`: package-local import of the grounded `web_search` extension runtime
  - includes the `web_search` tool plus `/web-search-status`, `/web-search-lock`, `/web-search-setup`, `/web-search-auth`, and `/web-search-backend`
  - persists the selected default backend and runs it first before preserving fallback across the remaining backends
