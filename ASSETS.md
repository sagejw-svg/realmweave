# Asset Provenance Ledger

Every art, audio, font, model, or data asset shipped with Realmweave must be
either original work or licensed for commercial use, and recorded here. This
protects a future MIT release and a potential paid Steam build. The rule:
**if it is not in this ledger with a clear license, it does not ship.**

Track assets from day one, even placeholders, so nothing unlicensed slips into a
build later.

## How to add an entry

For each asset (or asset pack), record: what it is, where it came from, the
license, whether commercial use and modification are allowed, the required
attribution text (if any), and where the license file lives in the repo.

## Code and rules

| Item | Source | License | Commercial | Notes |
|------|--------|---------|------------|-------|
| Realmweave source code | This project | MIT | Yes | See `LICENSE`. |
| Rules system (attributes, 1-100 skills, checks) | Original, D&D-*inspired* | MIT (our text) | Yes | Clean-room: our own names and numbers. Does not copy or depend on any third-party game content. |

## Local models (not bundled, user-installed)

Models are pulled by the user via Ollama, not shipped in the repo. Still verify
each one's license permits your intended use before recommending it in a release.

| Model | License | Commercial use | Notes |
|-------|---------|----------------|-------|
| Qwen2.5 (1.5B / 7B / 14B) | Check current model card | Verify before release | Router is model-agnostic; swap if a license is unfriendly. |
| Llama 3.1 8B | Meta Llama license | Has conditions | Review the acceptable-use and naming terms. |
| nomic-embed-text | Check current model card | Verify before release | Used for memory embeddings only. |

## Art, audio, fonts

*(none yet - the client currently draws primitives and uses the engine's
fallback font)*

| Item | Source | License | Commercial | Attribution | License file |
|------|--------|---------|------------|-------------|--------------|
| `godot_client/icon.svg` | Original (this project) | MIT | Yes | none | `LICENSE` |

## Reference note (not a dependency)

The official D&D System Reference Document 5.2.1 (2025) is available under
Creative Commons Attribution 4.0 International and is irrevocable. We have
**chosen not to depend on it** to avoid attribution and brand-adjacency
constraints. If any SRD-derived content is ever added, it must be listed here
with the required CC BY 4.0 attribution.

## Pre-release checklist

- [ ] Every shipped asset appears above with a license.
- [ ] All licenses permit commercial use and redistribution as configured.
- [ ] Required attributions are present in an in-game credits screen and/or
      `THIRD_PARTY_NOTICES`.
- [ ] No trademarked terms ("D&D", "Dungeons & Dragons", etc.) in the product
      name, store page, or marketing.
- [ ] Model licenses reviewed for any bundled or recommended model.
