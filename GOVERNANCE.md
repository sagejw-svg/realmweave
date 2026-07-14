# Realmweave Governance

Realmweave uses a simple, transparent model: a single head developer with final
authority, an open contributor community, and a hard, automated merge gate that
applies to everyone equally, including AI-assisted contributions.

## Roles

**Head developer / maintainer** - currently @sagejw-svg.
- Sets direction and owns `PROJECT_PLAN.md`.
- Triages and approves (or declines) every idea, bug, and code proposal.
- Is the required reviewer for all pull requests (via CODEOWNERS).
- Merges to `main`.

**Contributors** - anyone who submits an idea, bug, code, art, audio, docs, or
playtesting feedback. No special status required to participate.

**AI assistants** - Claude / Cowork and similar tools may draft plans, write
code, and open pull requests for `approved`, `ai-eligible` work. AI PRs go
through the exact same review gate as human PRs. AI is a contributor, not a
committer; it never bypasses review.

## How work flows

```
  Idea / Bug / Code proposal (guided issue form)
                 │
                 ▼
         label: needs-triage
                 │  head developer reviews
                 ▼
        approved  ──(+ ai-eligible if suitable)
                 │
                 ▼
   Implementation on a branch (contributor / maintainer / AI)
                 │
                 ▼
     Pull request  ──►  CI must pass (tests)  +  CODEOWNERS review
                 │
                 ▼
        Head developer approves and merges  →  main
```

Nothing reaches `main` without: (1) an approved intent, (2) green CI, and
(3) the head developer's review. This is enforced by branch protection, not just
convention.

## Labels

- `needs-triage` - new, awaiting the head developer.
- `idea`, `bug`, `code` - submission type.
- `approved` - green light to build.
- `ai-eligible` - a good fit for AI-assisted implementation.
- `help wanted` / `good first issue` - open for contributors to pick up.
- `wontfix` / `out-of-scope` - declined, with a reason in the thread.

## Decision principles

- **Vision first.** Changes must fit the emergent, local-first, autonomy-
  respecting design in `PROJECT_PLAN.md`.
- **Small and reversible.** Prefer focused changes with tests and a migration
  path for saved state.
- **Hard boundaries hold.** Some things are not up for debate (for example, no
  slavery or forced-labor mechanics; see `PROJECT_PLAN.md` section 13).
- **Transparency.** Approvals and declines happen in the open, with a reason.

## Changing this model

As the project grows, additional maintainers may be added by the head developer,
and this document updated by pull request. For now, the head developer has final
say.
