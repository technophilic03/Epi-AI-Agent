# Introduction

This is a lightweight local demo of AI Agent focusing on Epidemiological Research. It runs on macOS and Linux
with Python 3.12 and an OpenAI or Anthropic API key (or a self-hosted
OpenAI-compatible endpoint such as vLLM).
[Watch the demo video](https://drive.google.com/file/d/1A-N8pTOn6tKcZ_D6DLPc62EWvb2e_68E/view?usp=sharing)
## Start the demo

```bash
# Install uv if needed (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/xutao-wang/Epi-AI-Agent.git
cd Epi-AI-Agent

uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

cp .env.example .env
python study_installer.py --study report-india-synthetic-0.2.0.tar.gz
python run_fastapi.py
```

On the first native start, choose where to keep study data and local runtime
data, then choose the AI model provider (OpenAI, Anthropic Claude, or a custom
OpenAI-compatible endpoint). Re-open the provider menu any time with
`python run_fastapi.py --reconfigure`. These folders hold conversations,
uploads, generated datasets, and results; it is intentionally not committed.

You will then be asked to enter the API key for each provider backing the
configured models (OpenAI by default), so have it ready. Once verified, the
app prints the following local address:

<http://127.0.0.1:8000/>

## Model providers

Models are configured in `config/app.env`:

- `REPORT_AGENT_ALLOWED_MODELS` may mix OpenAI models (`gpt-*`, needs
  `OPENAI_API_KEY`), Anthropic models (`claude-opus-5`, `claude-sonnet-5`,
  `claude-haiku-4-5`, needs `ANTHROPIC_API_KEY`), and custom
  OpenAI-compatible models served by e.g. vLLM.
- `REPORT_AGENT_MODEL` selects the default model and must appear in the
  allowed list. The startup provider menu writes both values to `.env`;
  `--reconfigure` re-opens the menu.
- Custom endpoints are registered in `config/custom_models.json` (see
  `config/custom_models.example.json`): each entry names the endpoint's
  `base_url`, the served model name, optional token limits, and an optional
  `api_key_env` variable for its key.

Database extraction (DB-RAG semantic search) always embeds queries with
OpenAI, so it needs `OPENAI_API_KEY` even when chatting with Claude or a
custom model; without it the app still runs and reports database search as
not configured.

## Included demo data

The study uses a synthetic RePORT India database, its schema
catalog, a matching OpenAI embedding index, verified publication summaries, and
study-design metadata. No raw source data or original papers are included.

The `data/` folder also includes small synthetic CSV files and a matching
column dictionary for attachment and analysis demonstrations.

## Safety note

Local Python analysis is bounded for accidental or model-generated mistakes. It
is not a security sandbox for hostile code; use the demo only with files and
requests you trust.
