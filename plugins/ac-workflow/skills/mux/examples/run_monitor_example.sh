#!/bin/bash
# Quick demonstration of worker-monitor pattern for 2 directory analysis workers

set -e

echo "=========================================="
echo "Worker-Monitor Pattern Demonstration"
echo "=========================================="
echo ""
echo "This example demonstrates monitoring 2 background workers"
echo "analyzing a directory."
echo ""
echo "Pattern Requirements:"
echo "  - 2 Worker agents (run_in_background=True, agent_type='worker')"
echo "  - 1 Monitor agent (run_in_background=True, agent_type='monitor')"
echo "  - Monitor knows expected_count=2"
echo "  - All launched in same message batch"
echo ""
echo "=========================================="
echo ""

# Run the Python example
python3 ${CLAUDE_PLUGIN_ROOT}/skills/mux/examples/monitor_workers.py

exit_code=$?

echo ""
echo "=========================================="
if [ $exit_code -eq 0 ]; then
    echo "✓ Example completed successfully"
    echo ""
    echo "Key observations:"
    echo "  1. Workers launched with agent_type='worker'"
    echo "  2. Monitor launched with agent_type='monitor'"
    echo "  3. Monitor knows expected_count=2"
    echo "  4. Monitor polls signals until 2 completions detected"
    echo "  5. Summary aggregates findings from both workers"
else
    echo "✗ Example failed"
fi
echo "=========================================="

exit $exit_code
