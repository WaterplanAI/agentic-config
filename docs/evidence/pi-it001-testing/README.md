# Pi IT001 local testing evidence

## Scope

This directory records local validation evidence for the shipped pi package adoption surface, with emphasis on the repo-owned `@agentic-config/pi-ac-workflow` package and the migrated `tmux-agent` runtime.

## Evidence handling notes

- This file separates evidence that was directly observed in this session from evidence reported by the user during manual pi interaction.
- A local screenshot was shared for `/tmux-agent list`, but it is not copied into git because it contained unrelated local managed-agent names and project-specific runtime context.
- One MUX deliverable path was reported by the user but was not available to re-read from disk at documentation time, so that portion is preserved as user-reported evidence.

## Environment

- Repository: `agentic-config`
- Working branch during testing: `pi-adoption-it001`
- Local pi version observed in this session: `0.64.0`
- Primary package under test: `packages/pi-ac-workflow`

## Completed local testing steps

### Step 1 - Focused validation suite

Command run:

```bash
uv run pytest tests/test_tmux_agent_package_surface.py tests/test_canonical_generator.py -q
```

Directly observed result:

```text
.........                                                                [100%]
9 passed in 0.55s
```

What this proved:
- exact `tmux-agent` migration parity checks passed
- canonical generator smoke coverage passed
- package/readme/runtime surface assertions for the shipped scope passed

### Step 2 - Generator drift check

Command run:

```bash
uv run python tools/generate_canonical_wrappers.py --check
```

Directly observed result:

```text
Canonical outputs are up to date.
```

What this proved:
- committed generated outputs under `packages/` matched the canonical source under `canonical/`
- local pi smoke tests were run against synchronized package outputs, not stale generated files

### Pre-step install smoke observed directly in this session

Before the user-driven interactive pi checks, the following local install smokes were directly verified in fresh temp directories.

#### Direct local install of `pi-ac-workflow`

Command shape used:

```bash
pi install <repo-root>/packages/pi-ac-workflow -l
pi list
```

Directly observed project settings excerpt:

```json
{
  "packages": [
    "../../../../../../../../<repo-root>/packages/pi-ac-workflow"
  ]
}
```

Directly observed `pi list` excerpt:

```text
Project packages:
  ../../../../../../../../<repo-root>/packages/pi-ac-workflow
    <repo-root>/packages/pi-ac-workflow
```

#### Staged local install of `pi-all`

Command shape used:

```bash
pi install <tmp>/stage/pi-all -l
pi list
```

Directly observed project settings excerpt:

```json
{
  "packages": [
    "../../../../../../../../var/folders/.../stage/pi-all"
  ]
}
```

Directly observed `pi list` excerpt:

```text
Project packages:
  ../../../../../../../../var/folders/.../stage/pi-all
    /var/folders/.../stage/pi-all
```

What this proved:
- direct local install works for the standalone `pi-ac-workflow` package
- staged local install works for the bundled `pi-all` surface
- pi resolves the package roots from project-local `.pi/settings.json`

### Step 3 - Clean user-driven local install smoke for `pi-ac-workflow`

Command run:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
TEST_DIR="$(mktemp -d)"
cd "$TEST_DIR"
pi install "$REPO_ROOT/packages/pi-ac-workflow" -l
pi list
```

User-reported outcome:
- step completed successfully and testing continued from the same temp project in later steps

What this proved:
- the user was able to reproduce the package-local install smoke interactively, not just rely on the earlier assistant-run temp-dir verification

### Step 4 - Skill discovery in pi

Command run inside pi:

```text
/skill:ac-workflow-tmux-agent
```

User-shared result:

```text
Understood. I’ll follow the `ac-workflow-tmux-agent` skill for any long-lived agent work.

Key defaults I’ll use:
- `tmux_agent` tool only, not raw `tmux`/scripts
- headless by default
- open iTerm only if you want live visibility
- small, clear agent roles
- explicit hierarchy wiring only when needed
- `send_message` for parent→child, bounded reports for child→parent
- clean up finished agents with `kill` after harvesting output

If you want, I can now:
- spawn a new persistent agent
- open or revisit an existing one
- inspect status/tree
- send a message to a running agent
- kill managed agents cleanly

Just tell me what agent you want launched or managed.
```

What this proved:
- the shipped `ac-workflow-tmux-agent` skill loaded correctly from the local package install
- pi could render and apply the migrated skill instructions at runtime

### Step 5 - `/tmux-agent` command registration

Command run inside pi:

```text
/tmux-agent list
```

User-reported outcome:
- success, described as "Same with step 5"
- a screenshot was shared showing the managed tmux-agent list UI rendering correctly

Evidence preserved from the screenshot without copying the image itself:
- the `/tmux-agent list` command was recognized and rendered a managed-agent list view
- the view showed managed records in multiple states such as `terminated` and `missing`
- the view also showed a repo-summary worker entry consistent with the earlier smoke prompt

What this proved:
- the migrated extension registered the `/tmux-agent` command successfully
- the command surface was live, not just the markdown skill
- managed-agent registry data could be queried and rendered in pi

### Step 6 - Minimal headless spawn/completion smoke

Command run inside pi:

```text
/tmux-agent spawn "Inspect the current working directory, summarize what this project contains in 3 short bullets, then stop."
```

User-shared completion result:

```text
Working
Done — this run used `notificationMode: notify`, and the agent completed.

Summary:
- `agentic-config` is a monorepo for a project-agnostic AI development workflow system built around 7 workflow plugins.
- It also ships a parallel Pi package/distribution surface under `packages/`, plus a `canonical/` tree for generating shared multi-harness wrappers and assets.
- The repo includes supporting infrastructure like docs, tests, specs/roadmaps, git hooks, templates, and example/output folders.

Agent: `inspect-this-proje-20260407-120525`
Cleanup: session terminated after harvesting output.
```

What this proved:
- the migrated `tmux-agent` extension could spawn a managed headless worker end to end
- launch, execution, notification, completion harvest, and cleanup all worked in a local package install
- the migrated runtime was not only loadable, but operational

### Step 7 - Live running-worker spawn for inspection

Command run inside pi:

```text
/tmux-agent spawn "Use bash to run pwd, then sleep 20, then summarize the <project-path> in 2 short bullets and stop."
```

User-reported outcome:
- success, reported as `Working`
- the prompt intentionally kept the worker alive briefly so follow-up inspection commands could run before completion

What this proved:
- the migrated runtime can keep a managed worker alive long enough for live inspection
- the local package install supports the in-flight observability path, not only fast-completion tasks

### Step 8 - Live running-worker status and capture inspection

Commands run inside pi:

```text
/tmux-agent status <agent-id>
/tmux-agent capture <agent-id>
```

User-reported outcome:
- both commands succeeded, each reported as `Working`

What this proved:
- `/tmux-agent status` can inspect a running managed worker successfully
- `/tmux-agent capture` can retrieve a larger pane snapshot from a running managed worker successfully
- the migrated extension supports live observability, not just spawn/completion cleanup

### Step 9 - MUX protocol working example

User prompt run inside pi, anonymized for repo policy:

```text
/skill:ac-workflow-mux three-way coding-agent comparison
```

User-reported result summary, with session and deliverable slugs anonymized for repo policy:

```text
Completed under MUX.

- Session: `tmp/mux/<reported-session>`
- Deliverable: `tmp/mux/<reported-session>/deliverables/tool-comparison.md`
- Verification: `5/5` signals complete
```

User-shared deliverable summary, anonymized while preserving the evidence shape:

```text
Short version:

- **Pi** = best if you want a **customizable harness/framework** and are willing to build workflow features yourself.
- **External Tool A** = best if you want the most **built-in agent workflow UX** out of the box.
- **External Tool B** = best if your center of gravity is **CLI + hosted VCS + cloud/background automation**.

## Practical comparison

| Dimension | Pi | External Tool A | External Tool B |
|---|---|---|---|
| **Core posture** | Minimal, extensible harness | Built-in agentic coding workflow system | Multi-surface coding agent |
| **Extensibility** | Highest: extensions, skills, prompts, themes, packages | High: hooks, slash commands, skills, protocol integrations, plugins | High: protocol integrations, plugins, config-driven integrations |
| **Subagents** | Not built in | Built in | Built in |
| **Plan mode / planning UX** | Not built in | Explicitly documented planning-oriented workflows and permission modes | No separate plan mode was clearly called out in the upstream report |
| **Permissions / safety** | No built-in permission popups; you own the safety model | Strong built-in permission modes and protected-path controls | Approval policy + sandbox mode are core controls |
| **Execution modes** | Interactive TUI, print/JSON, RPC, SDK | Terminal/IDE/desktop/web, interactive + automated workflows | Interactive CLI, scripted exec, cloud/background, hosted VCS flows |
| **Programmatic integration** | Strongest as a framework: SDK + RPC | Some SDK-oriented integration surfaces | Strong automation story: exec, CI action, agent SDK guidance |
| **Best fit** | Toolsmiths / infra teams | Teams wanting built-in agent workflows | CLI/hosted-VCS/CI-heavy teams |

## My recommendation

### Choose **Pi** if
- you want to **own the runtime**
- you need **SDK/RPC embedding**
- you want to compose your own workflow with local code/config
- you’re okay building missing primitives like plan mode, permission gating, or subagent orchestration

### Choose **External Tool A** if
- you want **ready-made agentic workflows**
- built-in **subagents, hooks, protocol integrations, and permissions** matter
- you prefer a more productized experience over a framework

### Choose **External Tool B** if
- you want strong **CLI automation**
- hosted VCS and CI are central to your workflow
- cloud/background execution matters
- you want configurable autonomy via **approvals + sandboxing**

## The key difference in one sentence

- **Pi** is a **framework/harness**.
- **External Tool A** is a **productized agent workflow environment**.
- **External Tool B** is a **coding agent platform optimized for CLI/cloud/hosted-VCS automation**.

## Important caveat

This is docs-grounded, not a live benchmark. Some external-tool operational details remain uncertain unless you test them in your environment.

## Highest-value sources used

- Pi local docs: `<pi-install-root>/@mariozechner/pi-coding-agent/README.md`
- vendor A product and documentation pages covering overview, subagents, and permission modes
- vendor B product and documentation pages covering CLI, subagents, approvals/security, and cloud execution
```

Note:
- the original user-reported prompt, session slug, deliverable slug, and external vendor names were anonymized here to satisfy repo policy for git-tracked documentation.

What this proved:
- the shipped `ac-workflow-mux` surface could run a real multi-step comparison workflow
- the MUX protocol completed with `5/5` signals complete
- the workflow produced a concrete deliverable path and a structured synthesized result

## Current conclusion

Based on the directly observed results plus the user-reported manual pi interaction evidence captured above:

- canonical generation is in sync
- local package install works for `pi-ac-workflow`
- staged local install works for `pi-all`
- the migrated `ac-workflow-tmux-agent` skill loads correctly
- the migrated `/tmux-agent` command is registered and usable
- the migrated `tmux-agent` runtime can spawn, inspect, capture, complete, report, and clean up a managed worker
- the shipped `ac-workflow-mux` protocol can complete a real example workflow and produce a deliverable

## Remaining planned testing

Not yet captured in this evidence batch:
- additional staged `pi-all` manual skill-by-skill smoke coverage beyond the workflow package
