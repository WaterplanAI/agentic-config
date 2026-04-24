#!/usr/bin/env bash
# Test for issue #67: spec-resolver.sh and external-specs.sh fail under zsh
# because ${BASH_SOURCE[0]} is a bash-only array.
#
# Validates that:
#   1. All affected scripts use the ${BASH_SOURCE[0]:-$0} pattern (static check)
#   2. No bare ${BASH_SOURCE[0]} remains in self-location expressions
#   3. Scripts source correctly from arbitrary CWDs under bash (regression)
#   4. Scripts source correctly under zsh if zsh is available (primary fix)
#
# Why the fix works: BASH_SOURCE is a bash-only array. Under zsh it is unset,
# so ${BASH_SOURCE[0]:-$0} falls back to $0. zsh populates $0 with the sourced
# file path by default (FUNCTION_ARGZERO option on). bash never triggers the
# default because BASH_SOURCE[0] is always populated. Zsh-native alternatives
# such as ${(%):-%x} cannot be used because they are syntax errors under bash.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLUGINS=(
  "$REPO_ROOT/plugins/ac-git"
  "$REPO_ROOT/plugins/ac-workflow"
)

PASS=0
FAIL=0
SKIPPED=0
TOTAL=0

_test() {
  local name="$1"
  TOTAL=$((TOTAL + 1))
  echo "TEST $TOTAL: $name"
}

_pass() {
  PASS=$((PASS + 1))
  echo "  PASS"
}

_fail() {
  local msg="${1:-}"
  FAIL=$((FAIL + 1))
  echo "  FAIL: $msg"
}

_skip() {
  local msg="${1:-}"
  SKIPPED=$((SKIPPED + 1))
  echo "  SKIP: $msg"
}

# Run a subshell-isolated test case. Avoids A && B || C which conflates
# "case failed" with "_pass failed" (shellcheck SC2015).
_run_case() {
  local failmsg="$1"
  if "${@:2}"; then
    _pass
  else
    _fail "$failmsg"
  fi
}

# ---- Test 1: static - all affected files use the zsh-compatible pattern ----
_test "affected scripts use \${BASH_SOURCE[0]:-\$0} self-location pattern"
_case_1() {
  local missing=""
  local plugin rel file
  for plugin in "${PLUGINS[@]}"; do
    for rel in scripts/spec-resolver.sh scripts/external-specs.sh scripts/lib/source-helpers.sh; do
      file="$plugin/$rel"
      if [[ ! -f "$file" ]]; then
        missing="$missing $file(missing)"
        continue
      fi
      # Fixed-string search for the required fallback pattern. Single-quoted on
      # purpose so the shell does not expand it before grep sees it.
      # shellcheck disable=SC2016
      if ! grep -qF '${BASH_SOURCE[0]:-$0}' "$file"; then
        missing="$missing $file(no-fallback)"
      fi
    done
  done
  if [[ -n "$missing" ]]; then
    echo "Files missing fix:$missing" >&2
    return 1
  fi
  return 0
}
_run_case "one or more scripts still lack the BASH_SOURCE fallback" _case_1

# ---- Test 2: static - no bare ${BASH_SOURCE[0]} remains (without default) ----
_test "no bare \${BASH_SOURCE[0]} self-location without :-\$0 fallback"
_case_2() {
  local bad=""
  local plugin rel file lines
  for plugin in "${PLUGINS[@]}"; do
    for rel in scripts/spec-resolver.sh scripts/external-specs.sh scripts/lib/source-helpers.sh; do
      file="$plugin/$rel"
      [[ -f "$file" ]] || continue
      # Match ${BASH_SOURCE[0]} that is NOT followed by `:-$0`. A bare usage
      # without the fallback is the un-fixed bash-only pattern.
      lines=$(grep -nE '\$\{BASH_SOURCE\[0\]\}[^:]' "$file" || true)
      # Also match when the bare usage is the last thing on a line.
      lines="$lines$(grep -nE '\$\{BASH_SOURCE\[0\]\}$' "$file" || true)"
      if [[ -n "$lines" ]]; then
        bad="$bad\n  $file:\n$(printf '%s\n' "$lines" | sed 's/^/    /')"
      fi
    done
  done
  if [[ -n "$bad" ]]; then
    # shellcheck disable=SC2016
    printf 'Bare ${BASH_SOURCE[0]} usages remain:%b\n' "$bad" >&2
    return 1
  fi
  return 0
}
_run_case "bare \${BASH_SOURCE[0]} remains somewhere" _case_2

# ---- Test 3: functional (bash) - source spec-resolver.sh from unrelated CWD ----
_test "bash: source spec-resolver.sh from unrelated CWD resolves source-helpers.sh"
_case_3() {
  local TMPDIR_TEST plugin
  TMPDIR_TEST=$(mktemp -d)
  # shellcheck disable=SC2064 # expand TMPDIR_TEST now
  trap "rm -rf '$TMPDIR_TEST'" RETURN
  cd "$TMPDIR_TEST"

  for plugin in "${PLUGINS[@]}"; do
    unset -f load_agentic_config 2>/dev/null || true
    unset -f get_project_root 2>/dev/null || true
    unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
    # Source without setting CLAUDE_PLUGIN_ROOT: source-helpers.sh must
    # bootstrap it from BASH_SOURCE/$0. CWD is an unrelated tmpdir.
    # shellcheck source=/dev/null
    if ! source "$plugin/scripts/spec-resolver.sh" 2>/dev/null; then
      echo "failed to source $plugin/scripts/spec-resolver.sh from $TMPDIR_TEST" >&2
      return 1
    fi
    if [[ "$(cd "$CLAUDE_PLUGIN_ROOT" && pwd)" != "$(cd "$plugin" && pwd)" ]]; then
      echo "CLAUDE_PLUGIN_ROOT mismatch: got '$CLAUDE_PLUGIN_ROOT', expected '$plugin'" >&2
      return 1
    fi
  done
  return 0
}
_run_case "bash self-location broke when CWD differs from script dir" _case_3

# ---- Test 4: functional (bash) - source external-specs.sh from unrelated CWD ----
_test "bash: source external-specs.sh from unrelated CWD resolves source-helpers.sh"
_case_4() {
  local TMPDIR_TEST plugin
  TMPDIR_TEST=$(mktemp -d)
  # shellcheck disable=SC2064
  trap "rm -rf '$TMPDIR_TEST'" RETURN
  cd "$TMPDIR_TEST"

  for plugin in "${PLUGINS[@]}"; do
    unset -f load_agentic_config 2>/dev/null || true
    unset -f get_project_root 2>/dev/null || true
    unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
    # shellcheck source=/dev/null
    if ! source "$plugin/scripts/external-specs.sh" 2>/dev/null; then
      echo "failed to source $plugin/scripts/external-specs.sh from $TMPDIR_TEST" >&2
      return 1
    fi
  done
  return 0
}
_run_case "bash self-location broke when CWD differs from script dir" _case_4

# ---- Test 5: zsh (if available) - exact reproduction of issue #67 ----
_test "zsh: source spec-resolver.sh without errors (skipped if zsh unavailable)"
_case_5() {
  local TMPDIR_TEST plugin zsh_out
  TMPDIR_TEST=$(mktemp -d)
  # shellcheck disable=SC2064
  trap "rm -rf '$TMPDIR_TEST'" RETURN

  for plugin in "${PLUGINS[@]}"; do
    # Run a fresh zsh from an unrelated CWD, with CLAUDE_PLUGIN_ROOT cleared,
    # so self-location is exercised end-to-end. The reported failure was
    # "no such file or directory: <cwd>/lib/source-helpers.sh".
    if ! zsh_out=$(cd "$TMPDIR_TEST" && \
      env -u CLAUDE_PLUGIN_ROOT zsh -f -c \
        "source '$plugin/scripts/spec-resolver.sh' && \
         source '$plugin/scripts/external-specs.sh' && \
         echo RESOLVED=\$CLAUDE_PLUGIN_ROOT" 2>&1); then
      echo "zsh sourcing failed for $plugin:" >&2
      echo "$zsh_out" >&2
      return 1
    fi
    if ! printf '%s\n' "$zsh_out" | grep -q "^RESOLVED="; then
      echo "zsh did not print RESOLVED marker for $plugin:" >&2
      echo "$zsh_out" >&2
      return 1
    fi
    if printf '%s\n' "$zsh_out" | grep -qi "no such file or directory"; then
      echo "zsh still cannot locate source-helpers.sh for $plugin:" >&2
      echo "$zsh_out" >&2
      return 1
    fi
  done
  return 0
}
_zsh_sane() {
  # Probe that zsh (a) exists and (b) can actually execute a sourced file at
  # the paths this repo lives on. Skips broken Windows ports that do not
  # understand MSYS-style paths (e.g. scoop's unxutils 2007 zsh).
  command -v zsh >/dev/null 2>&1 || return 1
  local probe
  probe=$(mktemp) || return 1
  printf 'print ok\n' > "$probe"
  local out rc
  out=$(zsh -f -c "source '$probe'" 2>&1)
  rc=$?
  rm -f "$probe"
  [[ $rc -eq 0 && "$out" == "ok" ]]
}
if ! _zsh_sane; then
  _skip "zsh not installed or cannot source files on this host"
else
  _run_case "zsh sourcing produced the issue #67 failure mode" _case_5
fi

# ---- Test 6: expansion semantics - verify the fallback expression itself ----
_test "\${BASH_SOURCE[0]:-\$0} expansion semantics (default fires when empty)"
_case_6() {
  # Case A: BASH_SOURCE[0] populated (normal bash) -> uses BASH_SOURCE.
  # Observe this inside this test: the resolved path should end with this test's name.
  local observed
  observed="${BASH_SOURCE[0]:-$0}"
  case "$observed" in
    */test-issue-67-zsh-bash-source.sh) : ;;
    *)
      echo "bash: expected test file path, got '$observed'" >&2
      return 1
      ;;
  esac

  # Case B: prove the `:-` default mechanic that the fix depends on. bash will
  # not let us `unset BASH_SOURCE`, but we can blank BASH_SOURCE[0] in a
  # subshell and confirm ${BASH_SOURCE[0]:-FALLBACK} expands to FALLBACK. That
  # matches exactly what zsh sees (BASH_SOURCE unset/empty -> default fires).
  local fallback
  fallback=$(bash -c 'BASH_SOURCE[0]=""; printf %s "${BASH_SOURCE[0]:-FALLBACK}"')
  if [[ "$fallback" != "FALLBACK" ]]; then
    echo "bash: :- default did not fire when BASH_SOURCE[0] was empty, got '$fallback'" >&2
    return 1
  fi

  # Case C: under POSIX sh (dash), $0 inside an invoked script is the script
  # path. zsh with default FUNCTION_ARGZERO behaves the same way when sourcing
  # a file, so this gives us indirect evidence that the $0 leg of the fallback
  # resolves usefully on a non-bash shell. Skip if dash is unavailable.
  if command -v dash >/dev/null 2>&1; then
    local dash_script resolved
    dash_script=$(mktemp)
    # shellcheck disable=SC2064
    trap "rm -f '$dash_script'" RETURN
    cat > "$dash_script" <<'EOS'
printf '%s\n' "$0"
EOS
    resolved=$(dash "$dash_script")
    if [[ "$resolved" != "$dash_script" ]]; then
      echo "dash: \$0 did not resolve to script path, got '$resolved'" >&2
      return 1
    fi
  fi
  return 0
}
_run_case "fallback expression does not behave as designed" _case_6

# ---- Summary ----
echo ""
echo "==============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed, $SKIPPED skipped"
echo "==============================="

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
