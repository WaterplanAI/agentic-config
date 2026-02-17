# State Persistence

Workflow state management for resume capability.

## State File

Location: `{session}/workflow_state.yml`

## Schema

```yaml
# workflow_state.yml
session_id: "HHMMSS-xxxxxxxx"
command: "mux-ospec"
started_at: "2026-02-04T10:00:00Z"
updated_at: "2026-02-04T10:30:00Z"
status: "in_progress"

arguments:
  modifier: "full"
  spec_path: "/path/to/spec.md"
  cycles: 3
  phased: false

current_phase: 2
current_stage: "IMPLEMENT"
total_phases: 3

phases:
  - num: 1
    status: "completed"
    sc_contributions: ["SC-007"]
  - num: 2
    status: "in_progress"
    sc_contributions: ["SC-004", "SC-005"]

error_context: null
resume_instruction: "Resume with: /mux-ospec resume"
```

## Fields

| Field | Description |
|-------|-------------|
| session_id | Unique session identifier |
| command | Invoked command (mux-ospec) |
| started_at | Session start timestamp |
| updated_at | Last state update timestamp |
| status | in_progress, completed, failed, paused |
| arguments | Original invocation arguments |
| current_phase | Active phase number |
| current_stage | Active stage within phase |
| total_phases | Total phases from decomposition |
| phases | Per-phase status and contributions |
| error_context | Error details if failed |
| resume_instruction | User-facing resume command |

## Status Values

| Status | Description |
|--------|-------------|
| in_progress | Workflow actively executing |
| completed | All stages finished |
| failed | Unrecoverable error |
| paused | User-initiated pause |

## Resume Protocol

1. Read `workflow_state.yml`
2. Determine last completed stage
3. Resume from next stage
4. Update state on each transition

## Usage

```bash
# Resume interrupted workflow
/mux-ospec resume {session_path}
```

The orchestrator reads state and continues from last checkpoint.
