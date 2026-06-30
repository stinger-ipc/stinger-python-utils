---
name: release
description: "Release stinger-python-utils. Use when: releasing a new version, cutting a release, bumping the version, publishing, shipping, preparing a release, running pre-release checks."
argument-hint: "optional notes or release context"
---

# Release stinger-python-utils

Runs pre-release checks, bumps the version in `pyproject.toml`, then offers to commit and push.

## Procedure

### 1. Run mypy

```
uv run mypy src/ tests/
```

If mypy reports errors, fix them before continuing. Do not proceed until mypy is clean.

### 2. Run pytest

```
uv run pytest
```

If any tests fail, fix them before continuing. Do not proceed until all tests pass.

### 3. Bump the version

Read the current version from `pyproject.toml`. Then ask the user:

> The current version is `X.Y.Z`. How would you like to bump it?
> - **patch** → `X.Y.Z+1`
> - **minor** → `X.Y+1.0`
> - **major** → `X+1.0.0`
> - **manual** → enter a custom version string

Apply the chosen version to the `version` field in `pyproject.toml`.

### 4. Confirm commit and push

Ask the user:

> Ready to commit and push `vX.Y.Z` to `origin/main`?
> - **Yes** — stage `pyproject.toml`, commit with message `chore: bump version to X.Y.Z`, then push to `origin main`
> - **No** — stop here; leave the version bump in place for the user to handle manually

Only run `git add`, `git commit`, and `git push` if the user explicitly confirms.

### 5. Build

```
uv build
```

If the build fails, report the error and stop. Do not proceed to publish.

### 6. Confirm publish

Ask the user:

> Build succeeded. Publish `vX.Y.Z` to PyPI with `uv publish`?
> - **Yes** — run `uv publish`
> - **No** — stop here; the built artifacts are in `dist/`

Only run `uv publish` if the user explicitly confirms.
