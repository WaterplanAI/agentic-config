# CPC - Copy to Clipboard

Copies provided text to the macOS clipboard.

## Usage

```
/cpc <text to copy>
```

## Implementation

Execute:
```bash
cat << 'EOF' | pbcopy
$ARGUMENTS
EOF
```

Report: "Copied to clipboard."
