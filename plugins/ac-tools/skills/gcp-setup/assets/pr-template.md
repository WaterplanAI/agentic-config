## Summary

<!-- What does this PR do? -->

## Deploy to Stage

| Resource | Link |
|----------|------|
| Stage app | ${STAGE_URL} |
| Cloud Build console | [Build History](${CB_CONSOLE_URL}) |

### Steps

1. **Trigger the build** — comment on this PR:
   ```
   /gcbrun
   ```
2. **Approve the build** — open the [Cloud Build console](${CB_CONSOLE_URL}), find the pending build, and click **Approve**
3. **Wait for deploy** — build takes ~5 min; check status in the Checks tab above
4. **Verify** — open ${STAGE_URL} and confirm the app loads
5. **Health check**:
   ```bash
   curl ${STAGE_URL}${HEALTH_ENDPOINT}
   # Expected: see health_response in .gcp-setup.yml
   ```

> Repeat steps 1-2 after each push to this PR.
