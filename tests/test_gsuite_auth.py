#!/usr/bin/env python3
"""
Unit tests for gsuite auth.py CLI.

Tests account management functions without requiring real Google credentials.
Uses mocking for Google API interactions.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path


class TestResult:
    """Test result with pass/fail status."""

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


def get_repo_root() -> Path:
    """Get repository root directory."""
    return Path(__file__).parent.parent


def setup_test_config(temp_dir: Path) -> dict[str, str]:
    """Setup test configuration with temp directory."""
    config_dir = temp_dir / ".config" / "gsuite-skill"
    config_dir.mkdir(parents=True, exist_ok=True)
    accounts_dir = config_dir / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)

    # Create fake credentials.json
    creds = {
        "installed": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    (config_dir / "credentials.json").write_text(json.dumps(creds))

    return {"GSUITE_CONFIG_DIR": str(config_dir)}


def add_test_account(config_dir: Path, email: str) -> None:
    """Add a fake authenticated account."""
    account_dir = config_dir / "accounts" / email
    account_dir.mkdir(parents=True, exist_ok=True)

    # Create fake token
    token = {
        "token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
    }
    (account_dir / "token.json").write_text(json.dumps(token))


def run_auth_cli(args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    """Run auth.py CLI with given arguments."""
    repo_root = get_repo_root()
    auth_script = repo_root / "core" / "skills" / "gsuite" / "tools" / "auth.py"

    full_env = os.environ.copy()
    full_env.update(env)

    result = subprocess.run(
        ["uv", "run", str(auth_script)] + args,
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(repo_root),
    )

    return result.returncode, result.stdout, result.stderr


def test_status_no_accounts() -> TestResult:
    """Test status command with no authenticated accounts."""
    result = TestResult("status: no accounts shows setup instructions")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            env = setup_test_config(Path(temp_dir))
            returncode, _stdout, stderr = run_auth_cli(["status"], env)

            assert returncode == 0, f"Expected exit 0, got {returncode}"
            assert "No authenticated accounts" in stderr, "Missing no accounts message"

            result.mark_pass()
        except Exception as e:
            result.mark_fail(str(e))

    return result


def test_status_with_account() -> TestResult:
    """Test status command with an authenticated account."""
    result = TestResult("status: shows authenticated accounts")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            env = setup_test_config(Path(temp_dir))
            config_dir = Path(env["GSUITE_CONFIG_DIR"])

            # Add test account
            add_test_account(config_dir, "test@example.com")

            returncode, _stdout, stderr = run_auth_cli(["status"], env)

            assert returncode == 0, f"Expected exit 0, got {returncode}"
            assert "test@example.com" in stderr, "Account not shown in output"

            result.mark_pass()
        except Exception as e:
            result.mark_fail(str(e))

    return result


def test_status_json_output() -> TestResult:
    """Test status command with JSON output."""
    result = TestResult("status: JSON output format")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            env = setup_test_config(Path(temp_dir))
            config_dir = Path(env["GSUITE_CONFIG_DIR"])
            add_test_account(config_dir, "json@example.com")

            returncode, stdout, _stderr = run_auth_cli(["status", "--json"], env)

            assert returncode == 0, f"Expected exit 0, got {returncode}"

            # Parse JSON output
            data = json.loads(stdout)
            assert "accounts" in data, "Missing accounts key"
            assert "json@example.com" in data["accounts"], "Account not in JSON"

            result.mark_pass()
        except Exception as e:
            result.mark_fail(str(e))

    return result


def main() -> None:
    """Run all tests and report results."""
    print("Running gsuite auth.py tests...\n")

    tests = [
        test_status_no_accounts,
        test_status_with_account,
        test_status_json_output,
    ]

    results = []
    passed = 0
    failed = 0

    for test_func in tests:
        test_result = test_func()
        results.append(test_result)

        if test_result.passed:
            passed += 1
        else:
            failed += 1

        print(str(test_result))

    print(f"\nResults: {passed} passed, {failed} failed")

    if failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
