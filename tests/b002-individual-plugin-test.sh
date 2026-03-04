#!/usr/bin/env bash
# B-002: Individual Plugin Testing
# Requires interactive Claude CLI. Run each block manually.
# SC-3a: marketplace addable
# SC-3b: each plugin individually installable
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS=(ac-workflow ac-git ac-qa ac-tools ac-meta)

echo "=== SC-1: Validate marketplace ==="
echo "RUN: claude plugin validate '$REPO_ROOT'"
echo ""

echo "=== SC-3a: Add local marketplace ==="
echo "RUN: claude plugin marketplace add $REPO_ROOT"
echo ""

echo "=== SC-3b: Install each plugin individually ==="
for p in "${PLUGINS[@]}"; do
  echo "RUN: claude plugin install ${p}@agentic-plugins"
done
echo ""

echo "=== Per-plugin verification ==="
for p in "${PLUGINS[@]}"; do
  echo "--- Plugin: $p ---"
  echo "Load: claude --plugin-dir $REPO_ROOT/plugins/$p"
  echo "Check:"
  echo "  1. /help -- verify skills from $p appear"
  echo "  2. Skills discoverable (if plugin has skills/)"
  echo "  3. Agents visible in /agents (if plugin has agents/)"
  echo ""

  # Expected assets per plugin
  case "$p" in
    ac-workflow)
      echo "  Skills (6): mux, mux-ospec, mux-subagent, product-manager, spec, mux-roadmap"
      echo "  Agents: spec stage agents (CREATE, PLAN, IMPLEMENT, etc.)"
      echo "  Hooks (0): none"
      ;;
    ac-git)
      echo "  Skills (7): git-find-fork, git-safe, gh-assets-branch-mgmt, pull-request, release, branch, worktree"
      echo "  Hooks (1): git-commit-guard"
      ;;
    ac-qa)
      echo "  Skills (7): e2e-review, e2e-template, gh-pr-review, test-e2e, playwright-cli, browser, prepare-app"
      echo "  Hooks (0): none"
      ;;
    ac-tools)
      echo "  Skills (16): gsuite, human-agentic-design, had, cpc, dr, dry-run, single-file-uv-scripter,"
      echo "    ac-issue, adr, agentic-export, agentic-import, agentic-share, milestone, setup-voice-mode, video-query, improve-agents-md"
      echo "  Hooks (2): dry-run-guard, gsuite-public-asset-guard"
      ;;
    ac-meta)
      echo "  Skills (2): skill-writer, hook-writer"
      echo "  Hooks (0): none"
      ;;
  esac
  echo ""
done

echo "=== PASS/FAIL checklist ==="
echo "[ ] SC-1: claude plugin validate passes"
echo "[ ] SC-3a: marketplace added successfully"
for p in "${PLUGINS[@]}"; do
  echo "[ ] SC-3b: $p installed successfully"
  echo "[ ] $p: skills visible in /help"
  echo "[ ] $p: skills discoverable"
  echo "[ ] $p: agents visible (if applicable)"
done
