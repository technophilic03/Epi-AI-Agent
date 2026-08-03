# Epi AI Agent demo

This is a lightweight local demo of Epi AI Agent. It runs on macOS and Linux
with Python 3.12 and an OpenAI API key.

## Prerequisite: Python 3.12

Confirm that the required Python version is available:

```bash
python3.12 --version
```

If the command is unavailable, install Python 3.12 with your system package
manager. On macOS with Homebrew, run `brew install python@3.12`.

Without Homebrew on macOS, download and install Python 3.12 from the
[official Python macOS downloads page](https://www.python.org/downloads/macos/).

## Start the demo

```bash
git clone https://github.com/xutao-wang/Epi-AI-Agent.git
cd Epi-AI-Agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python study_installer.py --study report-india-synthetic-0.2.0
python run_fastapi.py
```

On the first native start, choose where to keep local runtime data. Press Enter
to use this project's `runtime/` folder. That folder holds conversations,
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
