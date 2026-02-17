# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
A2A Authentication Layer.

Supports bearer token authentication for A2A requests.
Tokens are validated against environment variable or config file.

SECURITY WARNING:
- Production deployments MUST configure tokens via A2A_BEARER_TOKENS env var or .a2a/tokens file
- Dev mode bypass (AGENTIC_MUX_DEV_MODE=true) allows ANY token - NEVER use in production
- Missing token configuration without dev mode = strict rejection (secure default)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_valid_tokens() -> set[str]:
    """Get set of valid bearer tokens.

    Sources (in order):
    1. A2A_BEARER_TOKENS env var (comma-separated)
    2. .a2a/tokens file (one per line)

    Returns:
        Set of valid token strings
    """
    tokens: set[str] = set()

    # From environment
    env_tokens = os.environ.get("A2A_BEARER_TOKENS", "")
    if env_tokens:
        tokens.update(t.strip() for t in env_tokens.split(",") if t.strip())

    # From file
    tokens_file = Path(".a2a/tokens")
    if tokens_file.exists():
        for line in tokens_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                tokens.add(line)

    return tokens


def verify_token(auth_header: str) -> bool:
    """Verify bearer token from Authorization header.

    Production mode (default): Requires exact token match against configured tokens
    Dev mode (AGENTIC_MUX_DEV_MODE=true): Bypasses validation, accepts any well-formed token

    Args:
        auth_header: Authorization header value (e.g., "Bearer token123")

    Returns:
        True if token is valid, False otherwise
    """
    if not auth_header:
        return False

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    token = parts[1].strip()
    if not token:
        return False

    # Check for explicit dev mode bypass
    dev_mode = os.environ.get("AGENTIC_MUX_DEV_MODE", "").lower() in {
        "true",
        "1",
        "yes",
    }

    if dev_mode:
        logger.warning("SECURITY: Dev mode active - bypassing token validation")
        return True

    valid_tokens = get_valid_tokens()

    # Production mode: require tokens to be configured
    if not valid_tokens:
        return False

    # Constant-time comparison to prevent timing attacks
    for valid_token in valid_tokens:
        if hmac.compare_digest(token, valid_token):
            return True

    return False


def generate_token() -> str:
    """Generate a new random bearer token.

    Returns:
        32-character hex token
    """
    return hashlib.sha256(os.urandom(32)).hexdigest()[:32]


def add_token(token: str) -> None:
    """Add a token to the tokens file.

    Args:
        token: Token to add
    """
    tokens_file = Path(".a2a/tokens")
    tokens_file.parent.mkdir(parents=True, exist_ok=True)

    existing = set()
    if tokens_file.exists():
        existing = {
            line.strip()
            for line in tokens_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    if token not in existing:
        with tokens_file.open("a") as f:
            f.write(f"{token}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A2A Token Management")
    parser.add_argument("action", choices=["generate", "add", "verify"])
    parser.add_argument("--token", help="Token for add/verify actions")
    args = parser.parse_args()

    if args.action == "generate":
        token = generate_token()
        print(f"Generated token: {token}")
        add_token(token)
        print("Token added to .a2a/tokens")
    elif args.action == "add":
        if not args.token:
            print("Error: --token required for add action")
        else:
            add_token(args.token)
            print("Token added")
    elif args.action == "verify":
        if not args.token:
            print("Error: --token required for verify action")
        else:
            header = f"Bearer {args.token}"
            valid = verify_token(header)
            print(f"Token valid: {valid}")
