#!/usr/bin/env bash
# Processes template files with variable substitution

# Process a template file with optional variable substitution
# Usage: process_template <template_file> <output_file> [VAR1=value1 VAR2=value2 ...]
process_template() {
  local template_file="$1"
  local output_file="$2"
  shift 2

  if [[ ! -f "$template_file" ]]; then
    echo "ERROR: Template not found: $template_file" >&2
    return 1
  fi

  # Start with template content
  local content
  content=$(cat "$template_file")

  # Process each VAR=value argument
  for arg in "$@"; do
    if [[ "$arg" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
      local var_name="${BASH_REMATCH[1]}"
      local var_value="${BASH_REMATCH[2]}"
      # Replace {{VAR_NAME}} with value (escape special chars for sed)
      local escaped_value
      escaped_value=$(printf '%s\n' "$var_value" | sed 's/[&/\|]/\\&/g')
      content=$(echo "$content" | sed "s|{{${var_name}}}|${escaped_value}|g")
    fi
  done

  # Write to output file
  echo "$content" > "$output_file"

  return 0
}
