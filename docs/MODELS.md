# LLM models: decisions and how to choose your own

This is the durable record of what Realmweave uses for AI, and how a player can
swap in their own models, including Claude or any API model.

## What we decided (and why)

Realmweave is **local-first**. AI runs on the player's machine by default, with a
GPU-free fallback so it always works. The router picks a model by the
*importance* of the moment, so most work is cheap and only big beats use a strong
model. Reference hardware: an RTX 5070 (12 GB).

| Tier | When it fires | Default model (Ollama) |
|------|---------------|------------------------|
| `reflex` | ambient one-liners, background chatter (importance <= 3) | `qwen2.5:1.5b-instruct` |
| `dialogue` | real conversations, reflections (3-7) | `qwen2.5:7b-instruct` |
| `narrative` | deaths, betrayals, world-shaping beats (> 7) | `qwen2.5:14b-instruct` |
| embeddings | memory relevance (RAG) | `nomic-embed-text` |
| fallback | no GPU / Ollama down | built-in deterministic **stub** |

These are defaults in `backend/config.json`. Nothing is locked in.

## Choosing your own models

### Option A - different local (Ollama) models

Pull any model with Ollama and set it in `config.json`. Examples: `llama3.1:8b`,
`mistral`, `qwen2.5:14b-instruct`, a bigger model if your VRAM allows.

```json
"models": {
  "reflex":    "qwen2.5:1.5b-instruct",
  "dialogue":  "llama3.1:8b",
  "narrative": "qwen2.5:14b-instruct"
}
```

### Option B - Claude, or any API model

Enable the `api` block. The key is read from an environment variable and is never
stored in the repo or save file. By default only the `narrative` tier uses the
API (rare, high-value moments), which keeps cost down; widen `tiers` to use it
more.

Claude:

```json
"api": {
  "enabled": true,
  "provider": "anthropic",
  "model": "claude-sonnet-5",
  "api_key_env": "ANTHROPIC_API_KEY",
  "tiers": ["narrative"]
}
```

Any OpenAI-compatible endpoint (OpenAI, OpenRouter, a local gateway, etc.):

```json
"api": {
  "enabled": true,
  "provider": "openai",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1",
  "api_key_env": "OPENAI_API_KEY",
  "tiers": ["narrative", "dialogue"]
}
```

Then set the key in your environment before starting the server:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # PowerShell
python run_server.py
```

If the API errors or is unreachable, the router falls back automatically to
Ollama, then the stub, so play never stops.

### Option C - "bring your own chat" via copy-paste (planned)

A no-API-key path: for rare narrative moments the game shows the exact prompt,
you paste it into Claude (or any chat model) in your browser, and paste the reply
back. This needs a small client UI (a prompt panel + a paste box) and is on the
list; the backend already has the seam (a pluggable API backend the router
calls). This is the pattern behind "connect the model just by pasting the prompt
into Claude."

## Notes

- **Local-first stays the default.** API is opt-in; the game is fully playable
  with zero keys and zero GPU (stub), or with Ollama for real local dialogue.
- **Cost control.** Because only chosen tiers hit the API, you can use a premium
  model for deaths and big decisions while everyday chatter stays local/free.
- **Model licenses:** verify any bundled/recommended model's license before a
  commercial release (see `ASSETS.md`). The router is model-agnostic on purpose.
