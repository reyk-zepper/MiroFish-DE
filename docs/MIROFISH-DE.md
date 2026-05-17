# MiroFish-DE

MiroFish-DE is a German-localized fork of [`666ghj/MiroFish`](https://github.com/666ghj/MiroFish).

## Goals

- German UI as default
- German backend/LLM language instruction as default
- Keep upstream updates mergeable via `upstream/main`
- Support OpenAI-compatible model providers:
  - local Ollama/vLLM
  - OpenAI API
  - OpenRouter
  - custom compatible endpoint

## Upstream update workflow

```bash
git remote -v
# origin   https://github.com/reyk-zepper/MiroFish-DE.git
# upstream https://github.com/666ghj/MiroFish.git

git fetch upstream
git checkout main
git merge upstream/main
npm run validate:locales
npm run build
```

If upstream adds new translation keys, update `locales/de.json` until `npm run validate:locales` passes.

## Provider selection

Copy `.env.example` to `.env` and set:

```env
LLM_PROVIDER=local
```

Valid values:

- `local` — Ollama/vLLM/OpenAI-compatible local server
- `openai` — official OpenAI API; requires `OPENAI_API_KEY`
- `openrouter` — OpenRouter; requires `OPENROUTER_API_KEY`
- `custom` — upstream-compatible `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME`

### Ollama example

```env
LLM_PROVIDER=local
LOCAL_LLM_API_KEY=dummy
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b-instruct
```

### vLLM example

```env
LLM_PROVIDER=local
LOCAL_LLM_API_KEY=dummy
LOCAL_LLM_BASE_URL=http://localhost:8000/v1
LOCAL_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
```

### OpenAI API example

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

A ChatGPT Pro subscription is not the same as API access. Server-side operation requires API access or a local/OpenAI-compatible endpoint.

## Remaining localization work

This first fork pass adds German translations and defaults. Some upstream source files still contain Chinese comments, developer logs, and deeper prompt text. The next hardening pass should move all user-facing prompt strings into locale files and keep internal comments/logs non-blocking.
