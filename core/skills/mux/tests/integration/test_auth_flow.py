#!/usr/bin/env python3
"""Integration tests for auth flow with A2A server."""
import os
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

# Import auth module
a2a_dir = Path(__file__).parent.parent.parent / "a2a"
auth_path = a2a_dir / "auth.py"

spec_auth = spec_from_file_location("auth", auth_path)
if spec_auth is None or spec_auth.loader is None:
    raise ImportError(f"Cannot load auth from {auth_path}")
auth = module_from_spec(spec_auth)
sys.modules["auth"] = auth
spec_auth.loader.exec_module(auth)

# Import symbols
verify_token = auth.verify_token
get_valid_tokens = auth.get_valid_tokens


def test_dev_mode_auth_flow():
    """Test dev mode authentication flow end-to-end."""
    # Setup: Enable dev mode
    os.environ["AGENTIC_MUX_DEV_MODE"] = "true"
    os.environ.pop("A2A_BEARER_TOKENS", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Simulate server request with any token
            auth_header = "Bearer dev-test-token-12345"
            authenticated = verify_token(auth_header)

            assert authenticated is True, "Dev mode should allow any token"

            # Simulate multiple requests with different tokens
            for token in ["token1", "token2", "random-string"]:
                auth_header = f"Bearer {token}"
                assert verify_token(auth_header) is True

        finally:
            os.chdir(old_cwd)
            os.environ.pop("AGENTIC_MUX_DEV_MODE", None)


def test_production_mode_auth_flow():
    """Test production mode authentication flow end-to-end."""
    # Setup: Production mode with configured token
    os.environ.pop("AGENTIC_MUX_DEV_MODE", None)
    os.environ["A2A_BEARER_TOKENS"] = "prod-token-abc123,prod-token-xyz789"

    try:
        # Valid token should authenticate
        assert verify_token("Bearer prod-token-abc123") is True
        assert verify_token("Bearer prod-token-xyz789") is True

        # Invalid token should fail
        assert verify_token("Bearer invalid-token") is False
        assert verify_token("Bearer ") is False
        assert verify_token("prod-token-abc123") is False  # Missing Bearer prefix

    finally:
        os.environ.pop("A2A_BEARER_TOKENS", None)


def test_production_mode_no_tokens_rejects():
    """Test production mode rejects all requests when no tokens configured."""
    # Setup: Production mode, no tokens
    os.environ.pop("AGENTIC_MUX_DEV_MODE", None)
    os.environ.pop("A2A_BEARER_TOKENS", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # All requests should be rejected
            assert verify_token("Bearer any-token") is False
            assert verify_token("Bearer secure-looking-token") is False

        finally:
            os.chdir(old_cwd)


def test_auth_flow_with_file_based_tokens():
    """Test authentication flow with file-based token configuration."""
    os.environ.pop("AGENTIC_MUX_DEV_MODE", None)
    os.environ.pop("A2A_BEARER_TOKENS", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Create .a2a/tokens file
            a2a_dir = Path(tmpdir) / ".a2a"
            a2a_dir.mkdir()
            tokens_file = a2a_dir / "tokens"
            tokens_file.write_text("file-token-001\nfile-token-002\n")

            # Valid tokens from file should authenticate
            assert verify_token("Bearer file-token-001") is True
            assert verify_token("Bearer file-token-002") is True

            # Invalid token should fail
            assert verify_token("Bearer wrong-token") is False

        finally:
            os.chdir(old_cwd)
