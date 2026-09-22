## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The problem this solves. -->

## How it was tested

<!-- Commands you ran and what they showed. Say which tier you could reach:
     offline tests only, or an actual run on hardware. -->

## Checklist

- [ ] `pytest` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] Tests added or updated for anything testable offline
- [ ] Heavy scientific imports stay inside functions, not at module level
- [ ] No credential, instance identifier or HPC account name in the diff or in
      any log pasted above
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
