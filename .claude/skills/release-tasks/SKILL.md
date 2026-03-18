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