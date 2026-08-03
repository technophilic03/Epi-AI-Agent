# Epi AI Agent demo

This is a lightweight local demo of Epi AI Agent. It runs on macOS and Linux
with Python 3.12 and an OpenAI API key.

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

On the first native start, choose where to keep study data and local runtime data. These folders hold conversations,
uploads, generated datasets, and results; it is intentionally not committed.

You will then be asked to enter your OpenAI API key, so have it ready. Once it
is verified, the app prints the following local address:

<http://127.0.0.1:8000/>

## Included demo data

The DB-RAG demo uses a synthetic RePORT India DuckDB database, its schema
catalog, a matching OpenAI embedding index, verified publication summaries, and
study-design metadata. No raw source data or original papers are included.

The `data/` folder also includes small synthetic CSV fixtures and a matching
column dictionary for attachment and analysis demonstrations.

## Safety note

Local Python analysis is bounded for accidental or model-generated mistakes. It
is not a security sandbox for hostile code; use the demo only with files and
requests you trust.
