---
name: release-publish
description: Finalize a release by merging the release branch into main and publishing a tagged GitHub release. Run this skill after release-tasks is complete.
---

# Release Publish

Run this skill after **release-tasks** has been completed successfully.

## 1. Merge the Release Branch into Main

Merge the release branch into `main` using a merge commit so the release is clearly visible in the history:

```bash
git checkout main
git merge --no-ff release-<version>
git push origin main
```

## 2. Publish the Release

Create a Git tag for the new version, push it to the remote, and create a GitHub release with the changelog entry for this version:

```bash
git tag v<version>
git push origin v<version>
```

## 3. Upload Distribution ZIPs

Attach the distribution ZIP archives (built during release-tasks step 9) to the GitHub release:

```bash
gh release upload v<version> dist/roboscope-offline-linux.zip
gh release upload v<version> dist/roboscope-offline-macos-arm64.zip
gh release upload v<version> dist/roboscope-offline-macos-x86_64.zip
gh release upload v<version> dist/roboscope-offline-windows.zip
gh release upload v<version> dist/roboscope-online.zip
```

Only upload ZIPs that were successfully built. If a platform build failed, note it in the release description.
