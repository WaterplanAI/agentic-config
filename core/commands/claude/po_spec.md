---
description: Phased o_spec orchestrator - decomposes large features into DAG phases
argument-hint: "[modifier] <spec_path|inline_prompt>|resume"
project-agnostic: true
---

# Phased Spec Orchestrator: /po_spec [modifier] <input>|resume

Multi-phase wrapper around `/o_spec` for large features requiring multiple iteration cycles.

# TASK

Decompose large features/bugs/chores into concrete phases, then orchestrate `/o_spec` execution for each phase with DAG-aware parallelization.

# ROLE & BEHAVIOR

- INVOKE `agent-orchestrator-manager` skill for delegation
- INVOKE `product-manager` skill for phase decomposition
- PROCEED autonomously - each phase produces fully functional code
- NEVER execute implementation directly - ALWAYS delegate via `/o_spec`

## CRITICAL RULES

- Phases form a DAG - respect dependencies, parallelize independents
- Each phase = one `/o_spec` cycle producing working code
- Parent state tracks phases; each phase has its own `/o_spec` state
- NO partial implementations - every phase is production-ready

# VARIABLES

Parse $ARGUMENTS to extract:
- MODIFIER: full (default), normal, lean, leanest - passed to child `/o_spec` calls
- INPUT: spec file path OR inline prompt describing the feature
- RESUME: if "resume" is passed, resume existing session

Examples:
- `/po_spec Add OAuth2 with RBAC` = decompose inline prompt, full modifier
- `/po_spec normal specs/big-feature.md` = decompose from spec, normal modifier
- `/po_spec resume` = resume in-progress session

# STATE PERSISTENCE

## Parent State Location

```
outputs/phases/{YYYY}/{MM}/{DD}/{HHMMSS}-{UUID}/
  manifest.yml          # Phase definitions from product-manager
  workflow_state.yml    # Parent orchestration state
  phase-{id}/           # Per-phase o_spec output directory
```

## Parent State Schema

```yaml
session_id: "HHMMSS-xxxxxxxx"
command: "po_spec"
started_at: "2025-12-22T10:00:00Z"
updated_at: "2025-12-22T12:30:00Z"
status: "in_progress"  # pending | in_progress | completed | failed

arguments:
  modifier: "normal"
  input: "Add OAuth2 with session management and RBAC"
  input_type: "inline"  # inline | file

manifest_path: "outputs/phases/2025/12/22/100000-abc12345/manifest.yml"
total_phases: 5
phases_completed: 2
phases_failed: 0

current_execution:
  batch: 2                    # Current parallel batch number
  phases: ["phase-3"]         # Phases in current batch
  in_progress: ["phase-3"]    # Currently executing

phases:
  - id: "phase-1"
    title: "Auth models and migrations"
    status: "completed"
    spec_path: "/absolute/path/to/spec.md"  # Resolved via spec-resolver.sh
    o_spec_config:
      modifier: "lean"
      model: null
      skip: []
    o_spec_session: "outputs/orc/2025/12/22/100500-def456"
    started_at: "2025-12-22T10:05:00Z"
    completed_at: "2025-12-22T10:25:00Z"
  - id: "phase-2"
    title: "OAuth provider integration"
    status: "completed"
    o_spec_config:
      modifier: "leanest"
      model: null
      skip: []
    dependencies: []
    # ...
  - id: "phase-3"
    title: "Auth flow endpoints"
    status: "in_progress"
    dependencies: ["phase-1", "phase-2"]
    # ...

execution_plan:
  - batch: 1
    phases: ["phase-1", "phase-2"]
    status: "completed"
  - batch: 2
    phases: ["phase-3"]
    status: "in_progress"
  - batch: 3
    phases: ["phase-4", "phase-5"]
    status: "pending"

error_context: null

bundles:
  # Generated from manifest bundles - tracks bundle execution
  - bundle_id: "bundle-batch1-group1"
    phases: ["phase-1", "phase-2"]
    status: "completed"  # pending | in_progress | completed | failed
    bundle_config:
      modifier: "lean"
      model: null
      skip: []
    spec_path: "specs/2025/12/feat/oauth/bundle-001-auth-models.md"
    o_spec_session: "outputs/orc/2025/12/22/100500-bundle1"
    started_at: "2025-12-22T10:05:00Z"
    completed_at: "2025-12-22T10:45:00Z"
  - bundle_id: "bundle-batch2-group1"
    phases: ["phase-4", "phase-5"]
    status: "pending"
    # ...

standalone_phases: ["phase-3"]  # Phases executed individually (high/critical)
resume_instruction: "Resume with: /po_spec resume"
```

# WORKFLOW

## PHASE 0: Session Check

Check for existing in-progress po_spec session:

```bash
for state_file in outputs/phases/*/*/*/*/workflow_state.yml; do
  if [ -f "$state_file" ]; then
    CMD=$(grep -E '^command:' "$state_file" | cut -d'"' -f2)
    STATUS=$(grep -E '^status:' "$state_file" | cut -d'"' -f2)
    if [ "$CMD" = "po_spec" ] && [ "$STATUS" = "in_progress" ]; then
      echo "Found: $state_file"
      cat "$state_file"
    fi
  fi
done 2>/dev/null
```

If found and user passed "resume": load and continue from current batch.
If found and user passed new input: ask to resume existing or start fresh.

## PHASE 1: Decomposition

**Invoke product-manager skill** with the input to generate phase manifest.

1. Create session directory:
```bash
SESSION_UUID=$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)
SESSION_ID="$(date +%H%M%S)-${SESSION_UUID}"
SESSION_DIR="outputs/phases/$(date +%Y/%m/%d)/${SESSION_ID}"
mkdir -p "$SESSION_DIR"

# Source spec resolver (pure bash - no external commands)
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"
```

2. Analyze input (file or inline prompt)
3. Decompose into phases following product-manager skill guidelines
4. Generate `manifest.yml` with:
   - Phase definitions (id, title, description, scope, acceptance_criteria)
   - Dependencies (hard/soft)
   - Spec prompts for each phase
   - o_spec_config per phase:
     - modifier: full | normal | lean | leanest
     - model: opus | sonnet | haiku (optional)
     - skip: list of stages to skip (optional)
   - Computed execution_order (parallel batches)

5. Create initial `workflow_state.yml`

## PHASE 2: Spec Generation

For each phase in manifest, generate a spec file:

```
# Resolve path for external/local routing
PHASE_SPEC=$(resolve_spec_path "{YYYY}/{MM}/{branch}/{NNN}-{phase-slug}.md")
```

Where NNN increments per phase (001, 002, etc.).

**Delegation Strategy**:

Spec creation is handled by `/o_spec` when the spec file doesn't exist. For each phase:

1. Build spec path: `PHASE_SPEC=$(resolve_spec_path "{YYYY}/{MM}/{branch}/{NNN}-{phase.slug}.md")`
2. `/o_spec` will invoke `/spec CREATE` if file is missing
3. Phase execution (PHASE 3) handles both spec creation and implementation

## PHASE 3: DAG Execution

Execute phases respecting dependency graph:

### Bundle Detection

Before executing each batch:
1. Load `bundles` from manifest
2. Identify which phases in current batch are bundled vs standalone
3. For bundled phases: execute bundle spec (single `/o_spec` cycle for all phases in bundle)
4. For standalone phases: execute individually (current behavior)

```
FOR each batch in execution_plan:
  1. Update state: current_execution.batch = batch_number
  2. Partition batch into bundles and standalone phases
  3. FOR each bundle in batch:
     a. Generate bundle spec file (if not exists) using BUNDLE SPEC TEMPLATE
     b. Update bundle status to "in_progress"
     c. INVOKE /o_spec {bundle_config.modifier} {bundle.spec_path}
     d. On completion: update bundle status + all bundled phases to "completed"
     e. On failure: update bundle status to "failed", set error_context
  4. FOR each standalone phase in batch (PARALLEL where multiple):
     a. Build o_spec invocation args from phase.o_spec_config:
        - MODIFIER = phase.o_spec_config.modifier (default: parent MODIFIER)
        - MODEL = phase.o_spec_config.model (optional)
        - SKIP = phase.o_spec_config.skip (optional, e.g., --skip=TEST,DOCUMENT)
     b. INVOKE /o_spec slash command:
        /o_spec {MODIFIER} {MODEL} {SKIP_FLAGS} {phase.spec_path}
     c. On completion: update phase status to "completed"
     d. On failure: update phase status to "failed", set error_context
  5. If any bundle or phase failed: STOP, report failure, preserve state for retry
  6. Update batch status to "completed"
  7. Proceed to next batch
```

### Command Invocation Pattern

For each phase, invoke `/o_spec` slash command:

```
# Build args from phase.o_spec_config
ARGS = "{phase.o_spec_config.modifier}"
if phase.o_spec_config.model:
    ARGS += " {phase.o_spec_config.model}"
if phase.o_spec_config.skip:
    ARGS += " --skip={','.join(phase.o_spec_config.skip)}"
ARGS += " {phase.spec_path}"

# Invoke
/o_spec {ARGS}
```

### Bundle Spec Generation

When generating a bundle spec file, use this template:

```markdown
# Human Section
Critical: any text/subsection here cannot be modified by AI.

## High-Level Objective (HLO)

{bundle.spec_title} - consolidated from {len(bundle.phases)} phases.

## Mid-Level Objectives (MLO)

{FOR each phase in bundle.phases}
{idx}. **{phase.title}**: {phase.scope[0]}
{ENDFOR}

## Details (DT)

{FOR each phase in bundle.phases}
### Phase {idx}: {phase.title}

{phase.description}

**Deliverables**:
{FOR each item in phase.scope}
- {item}
{ENDFOR}

**Acceptance Criteria**:
{FOR each criterion in phase.acceptance_criteria}
- {criterion}
{ENDFOR}

{ENDFOR}

## Behavior

Execute all phases sequentially within single implementation cycle. Each phase produces its deliverables before proceeding to the next.

# AI Section
Critical: AI can ONLY modify this section.
```

**Spec Naming**: Resolve path for external/local routing:
`BUNDLE_SPEC=$(resolve_spec_path "{YYYY}/{MM}/{branch}/bundle-{NNN}-{bundle-slug}.md")`

### Parallel Execution

When batch contains multiple phases with no inter-dependencies:
- Launch `/o_spec` calls concurrently using parallel `/spawn` invocations
- Monitor all, wait for completion
- Aggregate results before proceeding

### Sequential Fallback

If parallel execution is not feasible (model limitations, resource constraints):
- Execute batch phases sequentially
- Still respects cross-batch dependencies

## PHASE 4: Completion

When all phases complete:
1. Update parent state: `status: "completed"`
2. Generate summary report
3. List all spec files created
4. List all commits made (one per o_spec stage per phase)

# RESUME MECHANISM

On `/po_spec resume`:

1. Load most recent in-progress session
2. Identify current batch and phase status
3. Resume options:
   - Continue from current batch (default)
   - Retry failed phases: `/po_spec resume --retry-failed`
   - Skip to specific phase: `/po_spec resume --from=phase-3`
4. Re-execute incomplete phases

# ERROR HANDLING

## Phase Failure

If a phase's `/o_spec` cycle fails:
1. Mark phase as "failed" in parent state
2. Record error_context with details
3. Check if dependent phases can proceed (soft deps may continue)
4. For hard deps: halt dependent batches
5. Report status and await user decision

## Recovery Options

- **Retry phase**: `/po_spec resume --retry=phase-3`
- **Skip phase**: `/po_spec resume --skip=phase-3` (danger: may break deps)
- **Manual fix**: User fixes issue, then `/po_spec resume`

# REPORTING

After each batch completion, report:
- Completed phases (titles)
- Next batch phases
- Overall progress: `{completed}/{total} phases`
- Estimated remaining batches

# OUTPUT STRUCTURE

```
outputs/phases/2025/12/22/100000-abc12345/
  manifest.yml              # Phase definitions
  workflow_state.yml        # Parent orchestration state
  summary.md                # Final summary (generated on completion)

specs/2025/12/feat/oauth/
  001-auth-models.md        # Phase 1 spec
  002-oauth-provider.md     # Phase 2 spec
  003-auth-flow.md          # Phase 3 spec
  ...
```

# EXAMPLE EXECUTION

Input: `/po_spec Add OAuth2 authentication with session management and role-based access control`

1. **Decomposition** (product-manager skill):
   - Phase 1: Auth models & migrations (no deps)
   - Phase 2: OAuth provider config (no deps)
   - Phase 3: Auth flow endpoints (deps: 1, 2)
   - Phase 4: Session management (deps: 3)
   - Phase 5: RBAC middleware (deps: 1)
   - Phase 6: Integration & E2E tests (deps: 3, 4, 5)

2. **Execution Plan**:
   - Batch 1: [phase-1, phase-2] (parallel)
   - Batch 2: [phase-3, phase-5] (parallel - different dep chains)
   - Batch 3: [phase-4]
   - Batch 4: [phase-6]

3. **Execution**:
   - Batch 1: `/o_spec specs/.../001-auth-models.md` + `/o_spec specs/.../002-oauth-provider.md`
   - Wait for both...
   - Batch 2: `/o_spec specs/.../003-auth-flow.md` + `/o_spec specs/.../005-rbac.md`
   - ...continue until all phases complete

4. **Result**: 6 phases executed, each with full o_spec cycle (CREATE->DOCUMENT), all code production-ready.
