#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///
"""GSuite account management CLI for multi-account authentication."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

import typer
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from rich.console import Console
from rich.table import Table

# OAuth scopes for full access
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.activity.readonly",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts.other.readonly",
]

# Configuration
CONFIG_DIR = Path(os.environ.get("GSUITE_CONFIG_DIR", Path.home() / ".agents" / "gsuite"))
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
SERVICE_ACCOUNT_FILE = CONFIG_DIR / "service-account.json"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"
ACTIVE_ACCOUNT_FILE = CONFIG_DIR / "active_account"

app = typer.Typer(help="GSuite account management CLI.")
console = Console(stderr=True)
stdout_console = Console()


def get_config_dir() -> Path:
    """Get configuration directory, creating if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_active_account() -> str | None:
    """Get currently active account email."""
    # Check environment variable first
    env_account = os.environ.get("GSUITE_ACTIVE_ACCOUNT")
    if env_account:
        return env_account

    # Check active account file
    if ACTIVE_ACCOUNT_FILE.exists():
        return ACTIVE_ACCOUNT_FILE.read_text().strip()

    return None


def set_active_account(email: str) -> None:
    """Set the active account."""
    get_config_dir()
    ACTIVE_ACCOUNT_FILE.write_text(email)


def get_token_path(email: str) -> Path:
    """Get token file path for an account."""
    return ACCOUNTS_DIR / email / "token.json"


def list_accounts() -> list[str]:
    """List all authenticated accounts."""
    if not ACCOUNTS_DIR.exists():
        return []

    accounts = []
    for account_dir in ACCOUNTS_DIR.iterdir():
        if account_dir.is_dir() and (account_dir / "token.json").exists():
            accounts.append(account_dir.name)

    return sorted(accounts)


def _save_token_atomic(token_path: Path, creds: Credentials) -> None:
    """Save credentials atomically with file locking."""
    tmp_path: str | None = None
    try:
        with open(token_path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                with NamedTemporaryFile(
                    mode="w", dir=token_path.parent, delete=False, suffix=".tmp"
                ) as tmp:
                    tmp.write(creds.to_json())
                    tmp_path = tmp.name
                os.rename(tmp_path, token_path)
                tmp_path = None  # Successfully renamed, no cleanup needed
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


def load_credentials(email: str) -> Credentials | None:
    """Load credentials for an account, refreshing if needed."""
    token_path = get_token_path(email)

    if not token_path.exists():
        return None

    tmp_path: str | None = None
    try:
        with open(token_path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)

                # Handle expired credentials
                if creds and creds.expired:
                    if not creds.refresh_token:
                        console.print(
                            f"[yellow]Token expired for {email} and cannot be refreshed.[/yellow]"
                        )
                        console.print("Run [cyan]uv run auth.py add[/cyan] to re-authenticate.")
                        return None

                    try:
                        creds.refresh(Request())
                        # Atomic write: temp file + rename
                        with NamedTemporaryFile(
                            mode="w",
                            dir=token_path.parent,
                            delete=False,
                            suffix=".tmp",
                        ) as tmp:
                            tmp.write(creds.to_json())
                            tmp_path = tmp.name
                        os.rename(tmp_path, token_path)
                        tmp_path = None  # Successfully renamed, no cleanup needed
                    except Exception as e:
                        console.print(f"[red]Token refresh failed:[/red] {e}")
                        console.print("Run [cyan]uv run auth.py add[/cyan] to re-authenticate.")
                        return None

                return creds
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        console.print(f"[red]Error loading credentials for {email}:[/red] {e}")
        raise
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


def get_credentials(account: str | None = None) -> Credentials:
    """Get credentials for specified account or active account.

    Args:
        account: Optional email to use. If None, uses active account.

    Returns:
        Valid credentials for the account.

    Raises:
        typer.BadParameter: If no account specified/active, or no credentials found.
    """
    email = account or get_active_account()
    if not email:
        raise typer.BadParameter("No account specified and no active account configured")
    creds = load_credentials(email)
    if not creds:
        raise typer.BadParameter(f"No credentials found for {email}. Run: auth.py add")
    return creds


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show authenticated accounts and active account."""
    accounts = list_accounts()
    active = get_active_account()

    if json_output:
        result = {
            "accounts": accounts,
            "active": active,
            "config_dir": str(CONFIG_DIR),
            "credentials_exists": CREDENTIALS_FILE.exists(),
            "service_account_exists": SERVICE_ACCOUNT_FILE.exists(),
        }
        stdout_console.print_json(json.dumps(result))
        return

    if not accounts:
        console.print("[yellow]No authenticated accounts found.[/yellow]")
        console.print("\nTo add an account, run: [cyan]uv run auth.py add[/cyan]")
        console.print(f"Config directory: {CONFIG_DIR}")

        if not CREDENTIALS_FILE.exists():
            console.print(f"\n[red]Missing:[/red] {CREDENTIALS_FILE}")
            console.print("See assets/oauth-setup.md for setup instructions.")
        return

    table = Table(title="GSuite Accounts")
    table.add_column("Account", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Active", style="yellow")

    for account in accounts:
        creds = load_credentials(account)
        status_str = "Valid" if creds and not creds.expired else "Expired/Invalid"
        is_active = "*" if account == active else ""
        table.add_row(account, status_str, is_active)

    console.print(table)
    console.print(f"\nConfig: {CONFIG_DIR}")


@app.command()
def add(
    email: Annotated[str | None, typer.Argument(help="Email hint for account")] = None,
    credentials: Annotated[
        str | None,
        typer.Option("--credentials", "-c", help="Credentials file (name or path)"),
    ] = None,
    authuser: Annotated[
        int | None,
        typer.Option("--authuser", "-a", help="Google account index (0, 1, 2...) for multi-account browsers"),
    ] = None,
) -> None:
    """Add a new account via OAuth flow."""
    get_config_dir()

    # Resolve credentials file
    if credentials:
        creds_path = Path(credentials).expanduser()
        if not creds_path.is_absolute():
            creds_path = CONFIG_DIR / credentials
    else:
        creds_path = CREDENTIALS_FILE

    has_oauth = creds_path.exists()
    has_service = SERVICE_ACCOUNT_FILE.exists()

    if not has_oauth and not has_service:
        # Show BOTH options when neither credential type exists
        console.print("[yellow]No credentials configured.[/yellow]")
        console.print("\nChoose your authentication method:\n")

        console.print("[cyan]Option A: Personal OAuth[/cyan]")
        console.print("  For personal Google accounts")
        console.print(f"  Download credentials to: {creds_path}")
        console.print("  Guide: assets/oauth-setup.md\n")

        console.print("[cyan]Option B: Enterprise (Service Account)[/cyan]")
        console.print("  For Workspace domain-wide delegation")
        console.print(f"  Download key to: {SERVICE_ACCOUNT_FILE}")
        console.print("  Guide: assets/enterprise-setup.md")

        raise typer.Exit(1)

    if not has_oauth:
        # Service account exists but OAuth missing
        console.print(f"[red]Error:[/red] Missing {creds_path}")
        console.print("\nFor OAuth (personal accounts):")
        console.print("  See assets/oauth-setup.md")
        console.print(f"\n[dim]Service account detected at {SERVICE_ACCOUNT_FILE}[/dim]")
        console.print("[dim]Use 'auth status' to check enterprise setup.[/dim]")
        raise typer.Exit(1)

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_path),
            SCOPES,
        )

        console.print("[blue]Opening browser for authentication...[/blue]")

        if authuser is not None:
            # Manual flow to inject authuser parameter
            import webbrowser
            from wsgiref.simple_server import make_server

            # Generate authorization URL
            auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
            auth_url = f"{auth_url}&authuser={authuser}"

            console.print(f"[dim]Using authuser={authuser}[/dim]")

            # Start local server to receive callback (try multiple ports)
            host = "localhost"
            port = 8085
            server = None
            for try_port in [8085, 8086, 8087, 8088, 0]:
                try:
                    flow.redirect_uri = f"http://{host}:{try_port}/"
                    # Test by creating server (will be recreated below with wsgi_app)
                    from wsgiref.simple_server import make_server as _make_server
                    test_server = _make_server(host, try_port, lambda e, s: [])
                    port = test_server.server_port  # Get actual port (handles port=0)
                    test_server.server_close()
                    flow.redirect_uri = f"http://{host}:{port}/"
                    break
                except OSError:
                    if try_port == 0:
                        raise RuntimeError("Could not find available port for OAuth callback")
                    continue

            # Regenerate URL with correct redirect
            auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
            auth_url = f"{auth_url}&authuser={authuser}"

            # WSGI app to capture auth response
            auth_response = {}

            def wsgi_app(environ: dict, start_response):
                from urllib.parse import parse_qs

                query = environ.get("QUERY_STRING", "")
                params = parse_qs(query)
                auth_response["code"] = params.get("code", [None])[0]
                auth_response["state"] = params.get("state", [None])[0]

                start_response("200 OK", [("Content-Type", "text/html")])
                return [b"<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>"]

            server = make_server(host, port, wsgi_app)
            server.timeout = 120

            webbrowser.open(auth_url)

            # Wait for callback
            server.handle_request()
            server.server_close()

            if not auth_response.get("code"):
                if not auth_response:  # Empty dict means timeout
                    raise RuntimeError("Authentication timed out (120s). Please try again.")
                raise RuntimeError("No authorization code received")

            # Exchange code for token
            flow.fetch_token(code=auth_response["code"])
            creds = flow.credentials
        else:
            creds = flow.run_local_server(port=0)

        # Get user email from token info

        # Use userinfo endpoint to get email
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        account_email = user_info.get("email", email or "unknown")

        # Save token
        token_dir = ACCOUNTS_DIR / account_email
        token_dir.mkdir(parents=True, exist_ok=True)
        token_path = token_dir / "token.json"
        token_path.write_text(creds.to_json())

        # Set as active if no active account
        if not get_active_account():
            set_active_account(account_email)
            console.print("[green]Set as active account.[/green]")

        console.print(f"[green]Successfully authenticated:[/green] {account_email}")

    except Exception as e:
        error_str = str(e).lower()

        # Detect organization/external user OAuth errors
        org_mismatch_indicators = [
            "access_denied",
            "access blocked",
            "org_internal",
            "not in the list of allowed",
            "external users",
            "test user",
        ]

        is_org_mismatch = any(indicator in error_str for indicator in org_mismatch_indicators)

        if is_org_mismatch:
            console.print("[red]Access Blocked - Different Organization[/red]\n")
            console.print("The OAuth credentials were created in a different Google Cloud project.")
            console.print("Google blocks access because:\n")
            console.print("1. OAuth app is in 'testing' mode (not verified)")
            console.print("2. Only explicitly added 'test users' can use unverified apps")
            console.print("3. External org accounts aren't automatically allowed\n")

            console.print("[bold]Options:[/bold]\n")

            console.print("[cyan]Option A: Create separate credentials[/cyan] [yellow](Recommended)[/yellow]")
            console.print("  Create OAuth credentials in the organization's own GCP project")
            console.print("  1. Create/use GCP project under that organization")
            console.print("  2. Enable APIs and create OAuth credentials")
            console.print("  3. Download to: ~/.agents/gsuite/credentials-<org>.json")
            console.print("  4. See: assets/oauth-setup.md for detailed steps\n")

            console.print("[cyan]Option B: Add as test user[/cyan] (Low effort)")
            console.print("  Add the new account to your existing OAuth consent screen")
            console.print("  1. Go to: https://console.cloud.google.com/apis/credentials/consent")
            console.print("  2. Scroll to 'Test users' section")
            console.print("  3. Click 'Add Users' and enter the email")
            console.print("  4. Retry: uv run auth.py add\n")

            console.print("[dim]Option A is recommended for organizational accounts to avoid")
            console.print("ongoing test-user limitations and admin policy conflicts.[/dim]")
        else:
            console.print(f"[red]Authentication failed:[/red] {e}")

        raise typer.Exit(1)


@app.command()
def switch(
    email: Annotated[str, typer.Argument(help="Account email to switch to")],
) -> None:
    """Switch active account."""
    accounts = list_accounts()

    if email not in accounts:
        console.print(f"[red]Error:[/red] Account '{email}' not found.")
        console.print(f"Available accounts: {', '.join(accounts) if accounts else 'none'}")
        raise typer.Exit(1)

    set_active_account(email)
    console.print(f"[green]Switched to:[/green] {email}")


@app.command()
def remove(
    email: Annotated[str, typer.Argument(help="Account email to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove an account and its tokens."""
    accounts = list_accounts()
    if email not in accounts:
        console.print(f"[red]Error:[/red] Account '{email}' not found.")
        raise typer.Exit(1)

    token_dir = ACCOUNTS_DIR / email

    if not force:
        confirm = typer.confirm(f"Remove account '{email}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Remove token directory
    import shutil
    shutil.rmtree(token_dir)

    # Clear active account if it was this one
    if get_active_account() == email:
        ACTIVE_ACCOUNT_FILE.unlink(missing_ok=True)
        accounts = list_accounts()
        if accounts:
            set_active_account(accounts[0])
            console.print(f"[yellow]Switched active account to:[/yellow] {accounts[0]}")

    console.print(f"[green]Removed:[/green] {email}")


@app.command()
def token(
    email: Annotated[str | None, typer.Argument(help="Account email (default: active)")] = None,
) -> None:
    """Print access token for an account (for debugging)."""
    target = email or get_active_account()

    if not target:
        console.print("[red]Error:[/red] No active account. Run 'auth.py add' first.")
        raise typer.Exit(1)

    creds = load_credentials(target)

    if not creds:
        console.print(f"[red]Error:[/red] Could not load credentials for {target}")
        raise typer.Exit(1)

    if creds.expired:
        console.print("[yellow]Token expired, refreshing...[/yellow]")
        creds.refresh(Request())
        _save_token_atomic(get_token_path(target), creds)

    # Print token to stdout (not stderr)
    stdout_console.print(creds.token)


if __name__ == "__main__":
    app()
