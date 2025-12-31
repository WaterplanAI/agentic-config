# CREATE
STAGE: CREATE
GOAL: CREATE a NEW spec file from scratch based on user request, following the exact template and naming conventions.

## Variables
NONE (user provides objectives via conversation)

## Critical Compliance

- COMMIT ONLY the files you changed.
- USE EXACT TEMPLATE (see below).

## Behavior

- On "CREATE spec": enter PLANNING MODE.
- PROPOSE path using smart defaulting (see Path Defaulting Logic below).
- CREATE file using exact template below.
- COMMIT immediately using spec resolver (see Workflow step 9)

## Path Defaulting Logic

**Smart Default**: Use git history + current branch to suggest path.

1. PARSE current branch: extract version, component, feature.
2. SEARCH git log for recent specs on current branch:
   - `git log --oneline --all --grep="spec" --since="3 months ago"`
   - Look for patterns like `spec(NNN): CREATE - <title>`
3. IF specs found on current branch:
   - EXTRACT most recent bundle path (e.g., `specs/2025/11/004-v1.0.4-search-add_ai/`)
   - EXTRACT highest spec number (e.g., `028`)
   - PROPOSE: `<same_bundle>/<NNN+1>-<short-title>.md`
4. IF no specs found OR new branch:
   - ASK user: "No recent specs found. Use `/spec CREATE (new dir) <description>` or specify path?"
   - SUGGEST: `specs/<YYYY>/<MM>/<bundle>/001-<short-title>.md`
5. IF user provides explicit path:
   - ALWAYS use explicit path (overrides defaults).

**Decision Criteria**:
- REUSE bundle: incremental improvements, same component, shared context
- NEW bundle: major version bump, different component, architectural shift

## Workflow

1. USER requests spec creation (explicit or implicit).
2. ENTER PLANNING MODE.
3. EXTRACT high-level objective, mid-level objectives, and details from user conversation.
4. CAPTURE testing requirements:
   - Unit test expectations (what should be unit tested)
   - E2E test expectations (what should be integration/e2e tested)
   - Add to `## Details` section under `### Testing` if provided
5. APPLY smart path defaulting (see Path Defaulting Logic):
   - Check git history for recent specs on current branch
   - Propose next number in same bundle if found, OR ask user if new branch/no history
   - If user provides explicit path, use it directly
6. PRESENT proposed path and captured objectives to user.
7. CREATE file with exact template (see below), populating:
   - `## High-Level Objective` from user conversation (WHAT/WHY)
   - `## Mid-Level Objectives` from user conversation (HOW, action verbs)
   - `## Details` from user conversation (CONTEXT: constraints, files, behaviors)
   - `## Details ### Testing` if testing requirements were discussed
   - `## Behavior` if special AI instructions provided
8. VERIFY file created successfully.
9. COMMIT ONLY the new spec file using spec resolver:
   ```bash
   # Source spec resolver (pure bash - no external commands)
   _agp=""
   [[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
   AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
   unset _agp
   source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"

   # Commit spec changes
   commit_spec_changes "<spec_path>" "CREATE" "<NNN>" "<title>"
   ```
10. CONFIRM commit success.

## Spec File Template

SEE: @agents/spec/_template.md

## Path Naming Convention

- `<YYYY>`: Current year (4 digits)
- `<MM>`: Current month (2 digits, zero-padded)
- `<bundle>`: Logical grouping (e.g., `search`, `filtering`, `content`, `database`)
- `<NNN>`: Sequential spec number (3 digits, zero-padded) OR `000` for drafts
- `<short-title>`: Kebab-case descriptive title

## Example Paths

- `specs/2025/12/search/118-deterministic-long-summary.md`
- `specs/2025/12/filtering/119-nullable-content-date.md`
- `specs/2025/12/content/000-draft-extract-citations.md`

## Error Handling

- If sandbox blocks commit: ESCALATE to user immediately.
- If path already exists: WARN user, suggest alternative path.
- If unable to extract objectives: ASK user to clarify before proceeding.

## Output Format

After successful creation:
```
Created spec file: <absolute_path>
Commit: <commit_hash>
```
