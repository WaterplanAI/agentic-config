# Tier 2: Bounded Summary Extraction

Controlled context acquisition with 1KB hard cap.

## Tool

**Name**: `extract-summary.py` (Python script with PEP 723)

**Location**:
```bash
tools/extract-summary.py
```

## Usage

```bash
# Extract summary from single file (default 1KB cap)
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py {path}

# Custom byte limit
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py {path} --max-bytes 2048
```

## What Gets Extracted

1. Title (# heading)
2. Table of Contents
3. Executive Summary section
4. Everything up to first `---` separator

Typical output: 500-800 bytes
Hard cap: 1024 bytes (configurable)

## When to Use Tier 2

- Quality assessment of agent output
- Structure decisions (does output need splitting?)
- Error diagnosis (Executive Summary indicates issues)
- Coordinator deciding delegation strategy

## NEVER Do

- Use Read tool on output files
- Use unbounded head/tail/cat
- Skip Tier 1 verification first
- Read full files (only consolidation agent does this)
