Deploy the all-thing-eye project to AWS production server.

## Steps

### 1. Check for uncommitted changes

```bash
git status
```

If there are uncommitted changes, warn the user and stop. Do NOT commit automatically.

### 2. Detect which services changed

Compare the current branch against `origin/main` to detect changed services:

```bash
git diff --name-only origin/main...HEAD
```

Determine services to rebuild:
- Files under `frontend/` → `frontend`
- Files under `backend/`, `src/` → `backend`
- Files under `scripts/` → `backend` `weekly-bot`
- Files under `data-collector/` → `data-collector`
- `docker-compose.prod.yml`, `Dockerfile.*` → all services
- `nginx/` → `nginx`

If no service changes detected (only docs, config, etc.), ask the user whether to continue.

### 3. Git push

```bash
git push origin main
```

### 4. SSH deploy

SSH into the production server, pull changes, and rebuild only the changed services.

The SSH host alias `all-thing-eye` is pre-configured in `~/.ssh/config`.

```bash
ssh all-thing-eye "cd all-thing-eye && git pull && ./scripts/deploy.sh build <services>"
```

Replace `<services>` with the detected services (e.g., `backend frontend`).

Use a **10 minute timeout** for this command (`timeout: 600000`).

**Note:** The server's post-merge hook may show `/dev/tty` warnings — these are safe to ignore.

### 5. Verify health

Wait 20 seconds for services to start, then check health:

```bash
ssh all-thing-eye "cd all-thing-eye && docker compose -f docker-compose.prod.yml ps"
```

Also check the HTTP health endpoint:

```bash
curl -s --max-time 10 https://all.thing.eye.tokamak.network/health
```

### 6. Report result

Summarize to the user:
- Which services were rebuilt
- Container status (healthy/unhealthy)
- Health check result

## Notes

- SSH host alias `all-thing-eye` is configured in `~/.ssh/config`
- Only rebuild services that actually changed (saves time)
- If health check fails, show recent logs: `ssh all-thing-eye "cd all-thing-eye && docker compose -f docker-compose.prod.yml logs --tail=30 <failed-service>"`
- The `nginx` service usually does NOT need rebuilding (uses stock `nginx:alpine`), but needs restart if config changed: `ssh all-thing-eye "cd all-thing-eye && docker compose -f docker-compose.prod.yml restart nginx"`
