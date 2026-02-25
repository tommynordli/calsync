# Update Notification Design

## Goal

Prompt users to update calsync when new commits land on `main`.

## Constraints

- Only show the prompt on interactive CLI invocations (TTY check)
- Zero perceptible latency on CLI commands
- All failures silent — never break normal operation
- Max 1 remote check per day

## Components

### 1. Baked-in commit SHA

A setuptools build hook runs `git rev-parse HEAD` during `uv tool install` and writes `calsync/_commit.py`:

```python
COMMIT = "4d9ad7bae..."
```

This file is `.gitignore`d — it only exists in installed packages. A fallback `COMMIT = "unknown"` is used if the build hook can't determine the SHA.

### 2. Remote check during background sync

After `run_sync()` completes in `_cmd_sync()`, a function:

1. Checks the mtime of `~/.config/calsync/latest_commit`. If modified less than 24 hours ago, skips.
2. Hits `https://api.github.com/repos/tommynordli/calsync/commits/main` (unauthenticated, public repo).
3. Extracts the SHA from the JSON response.
4. Writes the raw SHA string to `~/.config/calsync/latest_commit`.
5. All wrapped in a bare `except` — any failure silently ignored.

### 3. Interactive CLI notification

In `main()`, after the command runs:

1. Check `sys.stdout.isatty()` — if not a TTY, skip.
2. Read `~/.config/calsync/latest_commit` — if missing/unreadable, skip.
3. Import `COMMIT` from `calsync._commit` — if import fails, skip.
4. Compare SHAs. If different, print:

```
Update available! Run: uv tool install --force "calsync @ git+https://github.com/tommynordli/calsync"
```

## Flow

```
launchd (every 15 min):
  -> calsync sync
  -> sync finishes
  -> is latest_commit file older than 24h?
     no  -> done
     yes -> GET github api -> write SHA to latest_commit -> done
     error -> silently ignored

user runs calsync interactively:
  -> command runs normally
  -> is stdout a TTY?
     no  -> done
     yes -> read latest_commit, compare to baked-in SHA
            different -> print one-liner
            same/error -> done
```

## Files to create/modify

- `calsync/_commit.py` — generated at build time (`.gitignore`d)
- `calsync/update_check.py` — new module with `check_for_update_remote()` and `check_for_update_local()`
- `calsync/cli.py` — call remote check after sync, local check in `main()`
- `pyproject.toml` — add build hook configuration
- `.gitignore` — add `_commit.py`
