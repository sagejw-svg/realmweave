# Contributing to Realmweave

Realmweave is an open, AI-augmented project: a head developer plus anyone who
wants to help, building a persistent living world. You do not need to be a
programmer to contribute. Ideas, bug reports, playtesting, art, music, and docs
are all real contributions. This guide explains how a suggestion becomes part of
the game.

## The short version

1. **Submit** an idea, bug, or code proposal using the guided forms
   (New issue -> pick a template). The forms prompt you for what we need.
2. **Triage.** New submissions are labeled `needs-triage`. The head developer
   reads every one.
3. **Approval.** If it fits the vision and roadmap, it gets the `approved` label.
   Nothing gets built or merged without this step. Good candidates for
   AI-assisted implementation also get `ai-eligible`.
4. **Build.** An approved item is implemented, by a contributor, the head
   developer, or via AI assistance (Claude / Cowork), always on a branch.
5. **Review gate.** The change opens a pull request. It must pass CI (tests) and
   be reviewed and approved by the head developer (enforced by CODEOWNERS and
   branch protection). The same gate applies to human and AI contributions alike.
6. **Merge.** Once green and approved, it lands on `main`.

This mirrors the model that makes projects like AetherSDR work: guided intake, a
human approval step, and a hard merge gate so `main` is always trustworthy.

## Ways to contribute

- **Ideas / features** - the 💡 Idea form. Tell us the problem and the proposal.
- **Bugs** - the 🐛 Bug form. Reproduction steps get things fixed fast.
- **Code** - the 🛠️ Code proposal form **first** (for anything non-trivial), so
  it can be approved before you spend time. Tiny obvious fixes can go straight to
  a PR.
- **Art, music, sound** - open an Idea issue; see `RESOURCES.md` for
  public-domain sources and `ASSETS.md` for how we log licenses.
- **Playtesting and docs** - run the headless sim or the client, tell us what
  felt off, or improve the guides.

## Approval: who decides, and by what standard

The **head developer** (@sagejw-svg) is the maintainer and final approver. See
`GOVERNANCE.md` for the full model. Decisions weigh:

- Fit with the vision in `PROJECT_PLAN.md` (emergent, local-first, agents keep
  their autonomy; the god influences but does not fully control).
- Scope and maintainability (small, focused changes are preferred).
- Whether it respects the project's hard boundaries (for example, no slavery or
  forced-labor mechanics; see `PROJECT_PLAN.md` section 13).

An approved idea is a green light to build. An unapproved or declined idea is not
a judgment of you; it may be out of scope, premature for the current phase, or
already planned.

## Developer setup

```bash
git clone https://github.com/sagejw-svg/realmweave
cd realmweave/backend
# core sim needs only the standard library; the server needs one package:
pip install -r requirements.txt
# run the world with no GPU:
python run_headless.py --ticks 144 --stub
```

On Windows the Python launcher is usually `py` instead of `python`.

## Submitting code (pull requests)

1. Fork the repo and create a branch: `feature/<short-name>` or `fix/<short-name>`.
2. Keep the change focused and matched to an **approved** issue (link it).
3. Run the checks locally from `backend/`:
   ```bash
   python -m compileall -q realmweave
   python -m unittest discover -s tests -p "test_*.py"
   ```
4. Add or update tests for the deterministic (stub) path where it makes sense.
5. If you changed saved state, bump `SAVE_VERSION` and keep a migration path so
   existing worlds still load.
6. Open a PR using the template. CI runs automatically; a maintainer reviews.

### Conventions

- **Commit messages:** short imperative subject, optionally a body. We use
  Conventional-Commit-style prefixes where natural (`feat:`, `fix:`, `docs:`,
  `chore:`, `test:`).
- **Style:** clear, well-commented Python. No em dashes in user-facing text; use
  hyphens sparingly (project style).
- **Determinism:** the simulation must stay reproducible given a seed and the
  stub LLM, so tests can rely on it.
- **Licensing:** only original or license-compatible assets, logged in
  `ASSETS.md`. See `RESOURCES.md`.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Thank you for helping build Realmweave.
