# Enterprise Setup Guide

Setup guide for Google Workspace domain-wide delegation (enterprise accounts).

## Overview

Domain-wide delegation allows a service account to impersonate users within a Workspace domain. This enables:
- No individual user consent required
- Automated access to organization resources
- Centralized credential management

## Prerequisites

- Google Workspace admin access
- Google Cloud project in organization

## Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create project in your organization
3. Go to IAM & Admin > Service Accounts
4. Click Create Service Account
5. Fill details:
   - Name: gsuite-skill-service
   - Description: GSuite skill service account
6. Click Create and Continue
7. Skip optional steps, click Done

## Step 2: Enable Domain-Wide Delegation

1. Click on the created service account
2. Go to Details tab
3. Under Advanced settings, click Show domain-wide delegation
4. Check Enable Google Workspace Domain-wide Delegation
5. Click Save
6. Note the Client ID (numeric, ~21 digits)

## Step 3: Create Service Account Key

1. Go to Keys tab
2. Click Add Key > Create new key
3. Select JSON
4. Click Create
5. Save the downloaded file securely

## Step 4: Configure Admin Console

1. Go to [Google Admin Console](https://admin.google.com/)
2. Navigate to Security > API Controls > Domain-wide delegation
3. Click Add new
4. Enter:
   - Client ID: (from Step 2)
   - OAuth scopes (comma-separated):
     ```
     https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/presentations
     ```
5. Click Authorize

## Step 5: Install Service Account Key

1. Create config directory:
   ```bash
   mkdir -p ~/.config/gsuite-skill
   ```

2. Move key file:
   ```bash
   mv ~/Downloads/project-*.json ~/.config/gsuite-skill/service-account.json
   ```

3. Set restrictive permissions:
   ```bash
   chmod 600 ~/.config/gsuite-skill/service-account.json
   ```

## Step 6: Configure Impersonation

For service accounts, set the account to impersonate via environment:

```bash
export GSUITE_IMPERSONATE_EMAIL="user@yourdomain.com"
```

Or add to your shell profile.

## Usage

With service account configured, the auth system will:
1. Detect service-account.json exists
2. Use domain-wide delegation
3. Impersonate the configured user

No OAuth browser flow required.

## Security Considerations

- Scope minimization: Only grant required scopes
- Key rotation: Rotate service account keys regularly
- Audit logging: Enable Cloud Audit Logs
- Least privilege: Limit which users can be impersonated

## Troubleshooting

### "Not authorized to access this resource"
- Verify domain-wide delegation is enabled
- Check Client ID matches in Admin Console
- Ensure scopes are authorized
- Verify impersonation email is valid user

### "Service account not found"
- Check service-account.json path
- Verify JSON format is correct
- Ensure file permissions allow reading

### "Invalid scope"
- Re-add scopes in Admin Console
- Wait 5-10 minutes for propagation
- Use exact scope URLs (no trailing slashes)
