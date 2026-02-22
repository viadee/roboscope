# E2E job fails: unknown option '--ignore' in Playwright test command

### Summary
The E2E workflow job fails due to the following error:

```
error: unknown option '--ignore=tests/take-screenshots.spec.ts'
```

### Details
- File: `.github/workflows/build.yml`
- Failing step: `Run E2E tests`
- Command: `cd e2e && npx playwright test --ignore=tests/take-screenshots.spec.ts`
- Run link: https://github.com/viadee-internal/roboscope/actions/runs/22282862238/job/64456216236

### Suggested Fix
Update the Playwright test run command to avoid using the unsupported `--ignore` option. Use `--grep-invert`, a shell pattern, or adapt the test suite as described:
- Example: `npx playwright test --grep-invert take-screenshots` (requires unique identifier in test name/describe)
- Or: use Bash extglob in file path (if supported by shell and structure)

---
Please adjust the workflow file accordingly to restore passing E2E tests.