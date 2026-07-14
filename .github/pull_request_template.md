<!-- Thanks for contributing to Realmweave! Fill this out so your PR can be reviewed quickly. -->

## What does this PR do?

<!-- A short description of the change. -->

## Linked issue

<!-- Every non-trivial PR should implement an APPROVED idea/bug/code proposal.
     Link it so a maintainer can see it was approved. -->
Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature / mechanic
- [ ] Refactor / internal
- [ ] Docs / assets
- [ ] Tests / CI

## How was it tested?

<!-- Unit tests added/updated? Headless acceptance run? Paste the command and result. -->

## Checklist

- [ ] This implements an **approved** issue (or is a trivial, obvious fix)
- [ ] `python -m unittest discover -s tests` passes from `backend/`
- [ ] I added or updated tests for the deterministic (stub) path where it makes sense
- [ ] If I changed saved state, I bumped `SAVE_VERSION` and kept a migration path
- [ ] I did not use em dashes in user-facing text (project style)
- [ ] The change respects agent autonomy and the vision in `PROJECT_PLAN.md`

## Notes for the reviewer

<!-- Anything the head developer should know before merging. -->
