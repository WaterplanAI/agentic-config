"""Shared test utilities for ac-safety tests."""

import sys


class TestResult:
    """Lightweight test result tracker for standalone test scripts."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: str | None = None

    def mark_pass(self) -> None:
        self.passed = True

    def mark_fail(self, error: str) -> None:
        self.passed = False
        self.error = error

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        msg = f"  {status}: {self.name}"
        if self.error:
            msg += f"\n    Error: {self.error}"
        return msg


def run_tests(name: str, tests: list) -> None:
    """Run a list of test functions and report results."""
    print(f"Running {name}...\n")
    passed = failed = 0
    for t in tests:
        result = t()
        print(result)
        if result.passed:
            passed += 1
        else:
            failed += 1
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} total")
    if failed:
        sys.exit(1)
    print("All tests passed!")
