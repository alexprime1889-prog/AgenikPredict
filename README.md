# AgenikPredict

**Universal Collective Intelligence Engine — Predict Anything**

AgenikPredict is an AI-powered prediction engine that uses multi-agent simulation to forecast outcomes from any unstructured data. Upload a report, describe a scenario, and watch millions of AI agents simulate the future.

## How It Works

```
Documents → Knowledge Graph → Agent Personas → Multi-Agent Simulation → Prediction Report
```

1. **Graph Construction** — Upload documents (PDF/MD/TXT). LLM extracts entities and relationships, builds a knowledge graph via GraphRAG
2. **Environment Setup** — AI generates agent personas from the graph, configures dual-platform simulation parameters
3. **Simulation** — Millions of agents interact on simulated Twitter + Reddit platforms in parallel
4. **Report Generation** — ReportAgent analyzes simulation data using 4 specialized tools (InsightForge, PanoramaSearch, QuickSearch, InterviewSubAgent)
5. **Deep Interaction** — Chat with any agent in the simulated world, or survey groups of agents

## Tech Stack

- **Frontend**: Vue 3 + Vite + D3.js + vue-i18n (5 languages)
- **Backend**: Python/Flask + OpenAI SDK
- **LLM**: Anthropic Claude via OpenRouter (configurable)
- **Memory**: Zep Cloud (temporal knowledge graph)
- **Simulation**: CAMEL-AI OASIS framework

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/AgenikPredict/agenikpredict.git
cd agenikpredict
npm run setup:all

# 2. Configure
cp .env.example .env
# Edit .env with your API keys (OpenRouter + Zep Cloud)

# 3. Run
npm run dev
# Frontend: http://localhost:3000
# Backend: http://localhost:5001
```

## Languages

AgenikPredict supports 5 languages with a built-in language switcher:
- English (default)
- Hebrew (RTL supported)
- Russian
- Spanish
- German

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | OpenRouter API key | — |
| `LLM_BASE_URL` | LLM API endpoint | `https://openrouter.ai/api/v1` |
| `LLM_MODEL_NAME` | Model ID | `anthropic/claude-sonnet-4.6` |
| `ZEP_API_KEY` | Zep Cloud API key | — |

## License

AGPL-3.0 — See [LICENSE](LICENSE) for details.

AgenikPredict is a modified version of [MiroFish](https://github.com/666ghj/MiroFish).
Original work Copyright (C) 2025 Guo Hangjiang / MiroFish Team.
Modifications Copyright (C) 2026 AgenikPredict Team.

See [NOTICE](NOTICE) and [MODIFICATIONS.md](MODIFICATIONS.md) for full attribution and changelog.
