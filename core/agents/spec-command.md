---
name: spec-command
description: Execute /spec workflow stages (RESEARCH, PLAN, IMPLEMENT)
argument-hint: <STAGE> <SPEC_PATH>
---

# /spec Command

Execute the /spec workflow according to `agents/spec/{STAGE}.md` instructions.

## Usage

```
/spec RESEARCH <spec_path>
/spec PLAN <spec_path>
/spec IMPLEMENT <spec_path>
```

Or with variable syntax:
```
/spec $ARGUMENTS
```
Where $ARGUMENTS = "<STAGE> <SPEC_PATH>" or $1=STAGE, $2=SPEC_PATH

## Instructions

RIGHT AFTER triggering this command:
1. RE-READ `./agents/spec/{STAGE}.md` (where STAGE is first argument)
2. RE-READ the spec file at SPEC_PATH (second argument, or last used spec if not provided)
3. REFLECT exact steps you will take based on your understanding
4. WAIT for explicit user confirmation ("OK" or equivalent)
5. EXECUTE the stage workflow as defined in the stage file
6. COMMIT ONLY the files modified during this stage

Refer to AGENTS.md for complete /spec workflow documentation.
