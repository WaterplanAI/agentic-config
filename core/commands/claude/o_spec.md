---
description: E2E spec orchestrator with workflow modifiers (full/normal/lean/leanest)
argument-hint: "[modifier] [--skip=STEPS] <spec_path|inline_prompt>"
project-agnostic: true
---

# E2E Spec Orchestrator: /o_spec [modifier] [model_override] <spec_path>|<inline_prompt>

# TASK

IMPLEMENT PRODUCTION-READY full autonomous end-to-end features/fixes/chores leveraging spec workflow with multi-agent orchestrator management skills.

# ROLE & BEHAVIOR

- INVOKE `agent-orchestrator-manager` skill.
- PROCEED autonomously without waiting for user confirmation unless explicitly requested by the user or a decision needs to be made that you cannot make yourself.
- ALWAYS execute the ENTIRE WORKFLOW, EVEN if SPEC is an inline_prompt.
- ENSURE EACH AGENT IN EACH STEP COMMITS ITS CORRESPONDING CHANGES TRACING PROGRESS IN GIT HISTORY.
    - PREPEND each commit message with `spec(NNN):`
- NO MVP APPROACHES/PLACEHOLDERS/later TODOs are allowed. EVERY implementation MUST be production-ready.
    - PENALIZE AGENTS who DON'T OBEY this.

## CRITICAL RULES

- ONLY use `/spec <STAGE> <path>` commands - NEVER invent custom instructions
- Format: `/spawn <model> "/spec <STAGE> <path> [ultrathink]"` - NOTHING ELSE
- Spec paths are resolved via `spec-resolver.sh` for external/local routing. Use relative path format: `specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`. PRIORITIZE using the spec path used in RECENT commits (branch).

# VARIABLES

Parse $ARGUMENTS to extract:
- MODIFIER: full (default), normal, lean, leanest
- MODEL_OVERRIDE: optional model name (opus/sonnet/haiku)
- SKIP_STEPS: optional --skip=STEP1,STEP2 flag
- SPEC: remaining arguments (file path or inline prompt)

Examples:
- `/o_spec specs/path.md` = full modifier
- `/o_spec normal specs/path.md` = normal modifier
- `/o_spec lean sonnet specs/path.md` = lean modifier with sonnet override
- `/o_spec leanest --skip=TEST,DOCUMENT specs/path.md` = leanest with skipped steps

NOTE: SPEC may be a file OR an inline-prompt.

# STATE PERSISTENCE

This command maintains workflow state in a YAML file for reliable resumption.

## State File Location

```
outputs/orc/{YYYY}/{MM}/{DD}/{HHMMSS}-{UUID}/workflow_state.yml
```

## State Schema

```yaml
session_id: "HHMMSS-xxxxxxxx"
command: "o_spec"
started_at: "2025-12-19T11:51:52Z"
updated_at: "2025-12-19T12:30:00Z"
status: "in_progress"

arguments:
  modifier: "normal"
  spec_path: "/absolute/path/to/spec.md"  # Resolved via spec-resolver.sh
  model_override: null
  skip_steps: []

current_stage: "IMPLEMENT"
current_step: 4
current_step_status: "in_progress"  # pending | in_progress | completed | failed
steps:
  - step: 1
    stage: "CREATE"
    status: "completed"
    started_at: "2025-12-19T11:51:52Z"
    completed_at: "2025-12-19T11:52:30Z"

error_context: null
resume_instruction: "Resume from IMPLEMENT with: /o_spec resume"
```

## Resume Behavior

- On command start: check for existing `in_progress` state for `o_spec`
- If found: display session info and ask user to resume or start fresh

**IMPORTANT**: When user selects "start fresh", create new session directory WITHOUT archiving old state.
Parallel agents from `/orc`, `/spawn`, or nested `/po_spec` may still be writing to existing sessions.
NEVER archive or modify in-progress sessions automatically. Sessions naturally become stale over time when
agents complete. Let the filesystem manage old sessions.

- On resume: load state, continue from `current_stage`/`current_step`

## State Update Protocol (AI-Interpreted)

State updates use a two-phase PRE/POST pattern for real-time visibility:

**PRE (before step execution):**
1. Set `current_step` to current step number
2. Set `current_stage` to current stage name
3. Set `current_step_status` to `"in_progress"`
4. Add/update step entry in `steps` with `status: "in_progress"`, `started_at: <timestamp>`
5. Update `updated_at` timestamp

**POST (after step completion):**
1. Set `current_step_status` to `"completed"`
2. Update step entry in `steps` with `status: "completed"`, `completed_at: <timestamp>`
3. Update `updated_at` timestamp
4. If final step: set `status: "completed"`

## Orchestrator Behavioral Constraint

**CRITICAL**: This command MUST maintain orchestrator role:
- ALWAYS delegate via `/spawn` command
- NEVER execute tasks directly (editing files, running tests, etc.)
- On user interruption: acknowledge feedback, update state, delegate corrective action via `/spawn`
- State file serves as context anchor preventing context loss

# MODIFIERS

## FULL (default)
Quality-first: Maximum oversight and planning rigor
- Uses: opus for critical stages (CREATE, RESEARCH, PLAN, PLAN_REVIEW, REVIEW)
- Uses: sonnet for execution stages (IMPLEMENT, TEST, DOCUMENT)
- All stages with ultrathink where applicable

## NORMAL
Balanced: Removes redundant review step
- Removes: PLAN_REVIEW stage
- Uses: opus for critical stages (CREATE, RESEARCH, PLAN, REVIEW)
- Uses: sonnet for execution stages (IMPLEMENT, TEST, DOCUMENT)
- All stages with ultrathink where applicable

## LEAN
Speed-focused: Reduced model costs, skips research
WARNING: Reduced quality vs speed tradeoff
- Removes: RESEARCH stage
- Uses: sonnet for all stages
- All stages with ultrathink where applicable

## LEANEST
Maximum speed: Minimal oversight, downgrades execution models
WARNING: Significantly reduced quality for maximum speed
- Removes: RESEARCH stage
- Uses: sonnet for planning/review (CREATE, PLAN, REVIEW)
- Uses: haiku for execution (IMPLEMENT, TEST, DOCUMENT)
- No ultrathink on haiku stages

# WORKFLOW

EXECUTE SEQUENTIALLY based on MODIFIER:

## SESSION INITIALIZATION

**BEFORE executing any workflow step**:

1. Check for existing in-progress state:
```bash
TODAY=$(date +%Y/%m/%d)
STATE_DIR="outputs/orc/$TODAY"
for state_file in "$STATE_DIR"/*/workflow_state.yml 2>/dev/null; do
  if [ -f "$state_file" ]; then
    CMD=$(grep -E '^command:' "$state_file" | cut -d'"' -f2)
    STATUS=$(grep -E '^status:' "$state_file" | cut -d'"' -f2)
    if [ "$CMD" = "o_spec" ] && [ "$STATUS" = "in_progress" ]; then
      echo "Found in-progress session: $(dirname "$state_file")"
      cat "$state_file"
    fi
  fi
done
```

**AI Decision**: If in-progress session found, ask user to resume or start fresh.

2. If starting fresh, create session directory and state file:
```bash
SESSION_UUID=$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)
SESSION_ID="$(date +%H%M%S)-${SESSION_UUID}"
SESSION_DIR="outputs/orc/$(date +%Y/%m/%d)/${SESSION_ID}"
mkdir -p "$SESSION_DIR"

# Source spec resolver (pure bash - no external commands)
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

# Resolve spec path - handles external/local routing
if [[ "$SPEC" == specs/* ]]; then
  RESOLVED_SPEC=$(resolve_spec_path "${SPEC#specs/}")
else
  RESOLVED_SPEC="$SPEC"  # Already absolute or external path
fi

cat > "$SESSION_DIR/workflow_state.yml" << EOF
session_id: "$SESSION_ID"
command: "o_spec"
started_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status: "in_progress"
arguments:
  modifier: "$MODIFIER"
  spec_path: "$RESOLVED_SPEC"
  model_override: "$MODEL_OVERRIDE"
  skip_steps: [$SKIP_STEPS]
current_stage: "CREATE"
current_step: 1
current_step_status: "pending"
steps: []
error_context: null
resume_instruction: "Resume with: /o_spec resume"
EOF
```

## FULL WORKFLOW
1. **State Update (PRE)**: Set current_step=1, current_stage=CREATE, current_step_status=in_progress
   /spawn opus "/spec CREATE {SPEC}" (SKIP if spec file exists)
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/01-create/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/01-create/summary.md"
2. **State Update (PRE)**: Set current_step=2, current_stage=RESEARCH, current_step_status=in_progress
   /spawn opus "/spec RESEARCH {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/02-research/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/02-research/summary.md"
3. **State Update (PRE)**: Set current_step=3, current_stage=PLAN, current_step_status=in_progress
   /spawn opus "/spec PLAN {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/03-plan/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/03-plan/summary.md"
4. **State Update (PRE)**: Set current_step=4, current_stage=PLAN_REVIEW, current_step_status=in_progress
   /spawn opus "/spec PLAN_REVIEW {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/04-plan_review/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/04-plan_review/summary.md"
5. **State Update (PRE)**: Set current_step=5, current_stage=IMPLEMENT, current_step_status=in_progress
   /spawn sonnet "/spec IMPLEMENT {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/05-implement/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/05-implement/summary.md"
6. **State Update (PRE)**: Set current_step=6, current_stage=REVIEW, current_step_status=in_progress
   /spawn opus "/spec REVIEW {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/06-review/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/06-review/summary.md"
7. **State Update (PRE)**: Set current_step=7, current_stage=TEST, current_step_status=in_progress
   /spawn sonnet "/spec TEST {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/07-test/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/07-test/summary.md"
8. **State Update (PRE)**: Set current_step=8, current_stage=DOCUMENT, current_step_status=in_progress
   /spawn sonnet "/spec DOCUMENT {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/08-document/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/08-document/summary.md", status=completed

## NORMAL WORKFLOW
1. **State Update (PRE)**: Set current_step=1, current_stage=CREATE, current_step_status=in_progress
   /spawn opus "/spec CREATE {SPEC}" (SKIP if spec file exists)
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/01-create/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/01-create/summary.md"
2. **State Update (PRE)**: Set current_step=2, current_stage=RESEARCH, current_step_status=in_progress
   /spawn opus "/spec RESEARCH {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/02-research/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/02-research/summary.md"
3. **State Update (PRE)**: Set current_step=3, current_stage=PLAN, current_step_status=in_progress
   /spawn opus "/spec PLAN {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/03-plan/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/03-plan/summary.md"
4. **State Update (PRE)**: Set current_step=4, current_stage=IMPLEMENT, current_step_status=in_progress
   /spawn sonnet "/spec IMPLEMENT {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/04-implement/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/04-implement/summary.md"
5. **State Update (PRE)**: Set current_step=5, current_stage=REVIEW, current_step_status=in_progress
   /spawn opus "/spec REVIEW {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/05-review/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/05-review/summary.md"
6. **State Update (PRE)**: Set current_step=6, current_stage=TEST, current_step_status=in_progress
   /spawn sonnet "/spec TEST {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/06-test/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/06-test/summary.md"
7. **State Update (PRE)**: Set current_step=7, current_stage=DOCUMENT, current_step_status=in_progress
   /spawn sonnet "/spec DOCUMENT {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/07-document/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/07-document/summary.md", status=completed

## LEAN WORKFLOW
1. **State Update (PRE)**: Set current_step=1, current_stage=CREATE, current_step_status=in_progress
   /spawn sonnet "/spec CREATE {SPEC}" (SKIP if spec file exists)
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/01-create/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/01-create/summary.md"
2. **State Update (PRE)**: Set current_step=2, current_stage=PLAN, current_step_status=in_progress
   /spawn sonnet "/spec PLAN {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/02-plan/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/02-plan/summary.md"
3. **State Update (PRE)**: Set current_step=3, current_stage=IMPLEMENT, current_step_status=in_progress
   /spawn sonnet "/spec IMPLEMENT {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/03-implement/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/03-implement/summary.md"
4. **State Update (PRE)**: Set current_step=4, current_stage=REVIEW, current_step_status=in_progress
   /spawn sonnet "/spec REVIEW {SPEC} ultrathink"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/04-review/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/04-review/summary.md"
5. **State Update (PRE)**: Set current_step=5, current_stage=TEST, current_step_status=in_progress
   /spawn sonnet "/spec TEST {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/05-test/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/05-test/summary.md"
6. **State Update (PRE)**: Set current_step=6, current_stage=DOCUMENT, current_step_status=in_progress
   /spawn sonnet "/spec DOCUMENT {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/06-document/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/06-document/summary.md", status=completed

## LEANEST WORKFLOW
1. **State Update (PRE)**: Set current_step=1, current_stage=CREATE, current_step_status=in_progress
   /spawn sonnet "/spec CREATE {SPEC}" (SKIP if spec file exists)
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/01-create/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/01-create/summary.md"
2. **State Update (PRE)**: Set current_step=2, current_stage=PLAN, current_step_status=in_progress
   /spawn sonnet "/spec PLAN {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/02-plan/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/02-plan/summary.md"
3. **State Update (PRE)**: Set current_step=3, current_stage=IMPLEMENT, current_step_status=in_progress
   /spawn haiku "/spec IMPLEMENT {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/03-implement/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/03-implement/summary.md"
4. **State Update (PRE)**: Set current_step=4, current_stage=REVIEW, current_step_status=in_progress
   /spawn sonnet "/spec REVIEW {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/04-review/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/04-review/summary.md"
5. **State Update (PRE)**: Set current_step=5, current_stage=TEST, current_step_status=in_progress
   /spawn haiku "/spec TEST {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/05-test/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/05-test/summary.md"
6. **State Update (PRE)**: Set current_step=6, current_stage=DOCUMENT, current_step_status=in_progress
   /spawn haiku "/spec DOCUMENT {SPEC}"
   **Agent Summary**: Request agent to write summary to: `{SESSION_DIR}/06-document/summary.md`
   **State Update (POST)**: Set current_step_status=completed, summary_path="{SESSION_DIR}/06-document/summary.md", status=completed

## STEP SKIPPING
If --skip flag provided, exclude specified steps from workflow.
Example: `--skip=TEST,DOCUMENT` removes steps 7-8 from full workflow

CAUTION: Skipping steps reduces quality assurance and documentation coverage.

# REPORT

REPORT PROGRESSIVE CONCISE YET INSIGHTFUL updates to me, your manager, as you progress through the workflow

# CONTROLS

## Resume Mechanism

If user interrupts workflow:
1. **Read state file**: Load `workflow_state.yml` from session directory
2. **Identify current position**: Use `current_stage` value (stage name, not step number)
3. **Resume options**:
   - `resume` - Continue from `current_stage` in state file
   - `resume from STAGE` - Override to specific stage (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, DOCUMENT)
4. **Update state**: On resume, update `updated_at` and continue workflow

**IMPORTANT**: Always resume by stage name, not step number. Step numbers vary by modifier (e.g., IMPLEMENT is step 5 in FULL, step 4 in NORMAL, step 3 in LEAN). The state file stores `current_stage` to ensure correct resumption regardless of modifier.

## Interruption Handling

When user provides feedback during execution:
1. Acknowledge the feedback
2. Update `error_context` in state file if applicable
3. Delegate corrective action via `/spawn` (NEVER execute directly)
4. Continue workflow from appropriate step

# NOTES

