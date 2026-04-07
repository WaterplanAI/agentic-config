# extensions

Package-local pi extensions exported by `@agentic-config/pi-ac-workflow`.

## Current extension set
- `tmux-agent/`
  - `index.ts`: exact repo-owned migration of the proven global `tmux-agent` extension
  - preserves the shipped `/tmux-agent` command and `tmux_agent` tool surface without narrowing the action set
  - preserves managed-session registry/audit state, private parent-child bridge flow, hierarchy/root tracking, managed visuals, debate channels, and peer-mode coordination

No other package-local workflow extensions currently ship from this package.
