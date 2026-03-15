# AgenikPredict — Modifications from MiroFish

This project is a modified version of [MiroFish](https://github.com/666ghj/MiroFish) by Guo Hangjiang / MiroFish Team.

## Changes Made

### Branding (March 2026)
- Full rebrand: MiroFish → AgenikPredict
- New logo integration (AGENIKAI brand)
- New landing page (Next.js + Magic UI + Reagraph)

### Internationalization (March 2026)
- Added vue-i18n v11 with 5 languages: English, Hebrew, Russian, Spanish, German
- 318 translation keys across all locale files
- Language switcher component with RTL support for Hebrew
- Backend LLM prompts respond in user's selected language via Accept-Language header

### Translation (March 2026)
- All ~655 Chinese strings translated to English across frontend and backend
- All backend Python comments, docstrings, log messages translated to English
- All LLM system prompts translated to English (with multilingual output support)

### UI/UX (March 2026)
- Dark theme applied across all views
- Magic UI animations: particles, fade-in, border-beam, text-shimmer
- Replaced Noto Sans SC (Chinese font) with Noto Sans Hebrew

### LLM Configuration (March 2026)
- Default LLM changed from Qwen (Alibaba) to Anthropic Claude via OpenRouter
- Default model: anthropic/claude-sonnet-4.6
- Updated .env.example with OpenRouter configuration

### Infrastructure (March 2026)
- New landing page: Next.js with Reagraph interactive knowledge graph
- Updated Dockerfile and docker-compose.yml
- Recreated Python virtual environment for new project structure

### Documentation (March 2026)
- New README.md in English
- ROADMAP.md with product development plan
- AGPL compliance documentation (NOTICE, MODIFICATIONS.md)
