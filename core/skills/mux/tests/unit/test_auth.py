#!/usr/bin/env python3
"""Unit tests for A2A authentication with dev mode security."""

import os
import tempfile
from pathlib import Path

# Import from parent
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "a2a"))

from auth import verify_token, generate_token, add_token, get_valid_tokens


def test_production_mode_no_tokens_configured():
    """Test that production mode rejects requests when no tokens configured."""
    # Clear all token sources
    os.environ.pop("A2A_BEARER_TOKENS", None)
    os.environ.pop("AGENTIC_MUX_DEV_MODE", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # No tokens configured, dev mode not enabled
            result = verify_token("Bearer test-token")
            assert result is False, "Production mode should reject all tokens when none configured"

            print("✓ Production mode no tokens test passed")
        finally:
            os.chdir(old_cwd)


def test_dev_mode_allows_any_token():
    """Test that dev mode explicitly allows any token when no tokens configured."""
    # Clear token sources
    os.environ.pop("A2A_BEARER_TOKENS", None)
    os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Dev mode enabled, no tokens configured
            result = verify_token("Bearer any-token-works")
            assert result is True, "Dev mode should allow any token"

            print("✓ Dev mode allows any token test passed")
        finally:
            os.chdir(old_cwd)
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_dev_mode_case_insensitive():
    """Test that dev mode env var is case-insensitive."""
    os.environ.pop("A2A_BEARER_TOKENS", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            for value in ["true", "True", "TRUE", "1", "yes", "YES"]:
                os.environ["AGENTIC_MUX_DEV_MODE"] = value
                result = verify_token("Bearer test")
                assert result is True, f"Dev mode should accept '{value}'"

            print("✓ Dev mode case insensitive test passed")
        finally:
            os.chdir(old_cwd)
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_production_mode_with_valid_token():
    """Test that production mode validates tokens when configured."""
    os.environ["A2A_BEARER_TOKENS"] = "valid-token-123"
    os.environ.pop("AGENTIC_MUX_DEV_MODE", None)

    try:
        # Valid token should succeed
        result = verify_token("Bearer valid-token-123")
        assert result is True, "Production mode should accept valid token"

        # Invalid token should fail
        result = verify_token("Bearer invalid-token")
        assert result is False, "Production mode should reject invalid token"

        print("✓ Production mode with valid token test passed")
    finally:
        os.environ.pop("A2A_BEARER_TOKENS", None)


def test_dev_mode_ignores_configured_tokens():
    """Test that dev mode bypasses token validation even when tokens configured."""
    os.environ["A2A_BEARER_TOKENS"] = "specific-token"
    os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

    try:
        # Any token should work in dev mode
        result = verify_token("Bearer any-token")
        assert result is True, "Dev mode should bypass token validation"

        print("✓ Dev mode ignores configured tokens test passed")
    finally:
        os.environ.pop("A2A_BEARER_TOKENS", None)
        os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_malformed_header():
    """Test that malformed headers are always rejected."""
    os.environ["AGENTIC_MUX_DEV_MODE"] = "true"

    try:
        # Missing Bearer prefix
        assert verify_token("token-without-bearer") is False

        # Empty header
        assert verify_token("") is False

        # Only "Bearer" without token
        assert verify_token("Bearer ") is False

        print("✓ Malformed header test passed")
    finally:
        os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_generate_token():
    """Test token generation produces valid format."""
    token1 = generate_token()
    token2 = generate_token()

    # Tokens should be 32 characters
    assert len(token1) == 32
    assert len(token2) == 32

    # Tokens should be unique
    assert token1 != token2

    # Tokens should be hex
    assert all(c in '0123456789abcdef' for c in token1)
    assert all(c in '0123456789abcdef' for c in token2)

    print("✓ Token generation test passed")


def test_add_token():
    """Test adding tokens to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Add first token
            add_token("token-001")
            tokens_file = Path(".a2a/tokens")
            assert tokens_file.exists()
            content = tokens_file.read_text()
            assert "token-001" in content

            # Add second token
            add_token("token-002")
            content = tokens_file.read_text()
            assert "token-001" in content
            assert "token-002" in content

            # Adding duplicate should not duplicate
            add_token("token-001")
            lines = [l.strip() for l in tokens_file.read_text().splitlines() if l.strip()]
            assert lines.count("token-001") == 1

            # Verify tokens are readable
            tokens = get_valid_tokens()
            assert "token-001" in tokens
            assert "token-002" in tokens

            print("✓ Add token test passed")
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    test_production_mode_no_tokens_configured()
    test_dev_mode_allows_any_token()
    test_dev_mode_case_insensitive()
    test_production_mode_with_valid_token()
    test_dev_mode_ignores_configured_tokens()
    test_malformed_header()
    test_generate_token()
    test_add_token()
    print("\n✓ All tests passed")
