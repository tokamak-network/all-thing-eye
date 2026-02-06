---
id: ssh-noninteractive-automation
name: SSH Non-Interactive Hook Automation
description: Use environment variables to bypass interactive prompts in git hooks when running via SSH/CI
source: ATI Support Bot deploy feature
triggers:
  - "/dev/tty: No such device or address"
  - "ssh deploy automation"
  - "git hook interactive prompt"
  - "non-interactive ssh"
  - "CI/CD git pull"
quality: high
---

# SSH Non-Interactive Hook Automation

## The Insight

When scripts read from `/dev/tty` for user input, they fail in non-interactive SSH sessions because no terminal is allocated. The solution is NOT to force a pseudo-terminal (`ssh -tt`), but to provide an **environment variable escape hatch** that the script checks before prompting.

## Why This Matters

CI/CD pipelines, automated deployments, and bots frequently need to run git operations remotely. If post-merge/post-checkout hooks prompt for user input, the automation fails with:
```
.git/hooks/post-merge: line XX: /dev/tty: No such device or address
```

## Recognition Pattern

You need this skill when:
- Building automated deployment via SSH
- Git hooks that prompt for options (deploy selection, confirmation)
- Any script that uses `read < /dev/tty` being called non-interactively

## The Approach

**Principle**: Give automated callers a way to pre-select choices via environment variables.

1. In the hook/script, check for an env var BEFORE prompting:
```bash
# Auto-deploy if AUTO_DEPLOY=1
if [ "$AUTO_DEPLOY" = "1" ]; then
    # Execute the default/desired action directly
    ./scripts/deploy.sh build "${SERVICES[@]}"
    exit 0
fi

# Otherwise, prompt interactively as usual
echo -n "Choice: "
choice=$(read_input)
```

2. Call from automation with the env var:
```bash
ssh server "cd project && AUTO_DEPLOY=1 git pull"
```

**Key Benefits**:
- Manual usage unchanged (no env var = normal prompt)
- Automation gets deterministic behavior
- No need for `expect`, `ssh -tt`, or piping input

## Example

```python
# Python subprocess call for automated deploy
ssh_commands = """
cd all-thing-eye && \
AUTO_DEPLOY=1 git pull
"""
subprocess.run(["ssh", "server", ssh_commands])
```

The hook detects `AUTO_DEPLOY=1` and skips the interactive prompt, executing the desired action automatically.
