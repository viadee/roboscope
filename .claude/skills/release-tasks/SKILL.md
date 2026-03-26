---
name: release-tasks
description: Prepare a new release: bump the version, verify the Docker build, create a release branch, run all tests (backend, frontend, E2E), and update the changelog, README, and in-app documentation. Run this skill before release-publish.
---

# Release Tasks

Complete these steps in order to prepare a release. When everything here is done, run the **release-publish** skill to merge and tag.

## 1. Bump the Version

Update the version number in the project's configuration files. Version numbers follow semantic versioning (major.minor.patch, e.g., `1.0.0`). Increment the appropriate part based on the changes since the last release.

## 2. Update and Check the Docker Build

Review the docker-compose files used to set up the development environment and verify that they work correctly.

## 3. Create a Release Branch

Create a release branch from the main development branch (e.g., `main`). Name it after the version being released (e.g., `release-1.0.0`). Use this branch for all remaining steps.

## 4. Run Backend and Frontend Tests

Run the full unit and integration test suites:

```bash
make test-backend   # pytest
make test-frontend  # Vitest
```

Fix any failures before proceeding.

## 5. Run E2E Tests

Run the end-to-end (E2E) tests to verify that the software works correctly end-to-end. Fix any issues that arise.

```bash
make test-e2e
```

## 6. Update the Changelog

Update `CHANGELOG.md` with all notable changes since the last release. List them in chronological order under the new version number.

## 7. Update README.md

If the project's functionality or usage has changed, update `README.md` to reflect those changes.

## 8. Update the Frontend Documentation

If the project's functionality or usage has changed, update the in-app documentation under `frontend/src/docs/` to reflect those changes. The documentation is available in four languages (EN, DE, FR, ES) — update all affected languages.

## 9. Build and Test Distribution ZIPs

Build the standalone offline distribution archives for all platforms and verify they work:

```bash
# Build for each platform
bash scripts/build-mac-and-linux.sh linux
bash scripts/build-mac-and-linux.sh macos-arm64
bash scripts/build-mac-and-linux.sh macos-x86_64
bash scripts/build-mac-and-linux.sh windows

# Also build the online (lightweight) variant
bash scripts/build-online-mac-and-linux.sh
```

Verify:
- All ZIPs are created under `dist/`
- Spot-check at least one ZIP: extract it, confirm it contains `frontend_dist/`, `backend/`, install/start scripts, and wheels
- Ensure the version in the built artifacts matches the release version

## 10. Smoke-Test the Distribution ZIP

Before releasing, do a real smoke-test of the built archive for the current platform:

```bash
# 1. Extract the ZIP into a temporary directory
SMOKE_DIR=$(mktemp -d)
unzip dist/roboscope-offline-*.zip -d "$SMOKE_DIR"
cd "$SMOKE_DIR/roboscope-offline-"*

# 2. Run the install script (macOS/Linux)
bash install.sh
# On Windows: install-windows.bat

# 3. Start the server
bash start.sh &
# On Windows: start-windows.bat

# 4. Wait for startup and verify
sleep 5
curl -sf http://localhost:8145/api/v1/health && echo "Health OK"
curl -sf http://localhost:8145/ | head -5 && echo "Frontend OK"

# 5. Clean up
kill %1 2>/dev/null
rm -rf "$SMOKE_DIR"
```

Verify:
- Install script completes without dependency resolution errors
- Server starts and responds on the configured port
- Frontend is served correctly
- Health endpoint returns OK

If the smoke-test fails (e.g., missing wheels, dependency conflicts), fix the build script and rebuild before proceeding.