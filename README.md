# RePORT Agent working demo

This branch packages the FastAPI application and its prebuilt browser UI for
local use on macOS and Linux. Participants need Python 3.12 and an OpenAI API
key. They do not need Node.js, npm, test tooling, source datasets, or container
software.

## Install

```bash
git clone -b working-demo --single-branch https://github.com/xutao-wang/RePORT-agent.git
cd RePORT-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your-key
```

Install a separately supplied study archive, then start the application:

```bash
python study_installer.py --study /path/to/study.tar.gz
python run_fastapi.py
```

`--study` accepts multiple archive paths in one transactional installation.
Multiple active studies can be loaded, but semantic routing between them is not
part of this release; select the study explicitly when more than one is active.
Without an installed study package, the app still starts with its generic
capabilities. The study installer and FastAPI application use that same folder
from `REPORT_AGENT_STUDY_ROOT`: the installer writes packages there and
FastAPI reads packages there. `--study-root` overrides it for a single
installer command. The installer asks where study packages should be stored on
its first run and saves the chosen absolute path in the untracked `.env` file.

The native launcher separately asks where RePORT Agent should keep local
conversation state, uploaded files, and generated datasets. It saves that
choice as `REPORT_AGENT_RUNTIME_ROOT`. The default locations are `study_data/`
for packages and `runtime/` for app state.

Then open <http://127.0.0.1:8000/>.

## Saved conversations and local data

The browser starts on a new blank conversation after a reload or a newly opened
tab. Earlier conversations remain available in **Saved conversations** in the
sidebar. Select one to reopen its exact thread and its locked model choice.
**Reset Conversation** only clears the current browser view; it does not delete
the saved thread, messages, generated datasets, figures, or files.

Every accepted first message records the conversation in the local checkpoint
database. RePORT Agent generates a short intent title with the configured title
model; you can rename a saved conversation, and a manual title is preserved.
The model picker beside Send is available before the first message and is locked
for the rest of that conversation. Other runtime settings stay in
config/app.env.

The selected runtime folder contains local checkpoints and run artifacts. Keep
that folder to continue prior work; deleting it removes the local data. Docker
uses its configured volume instead of this native first-run prompt.

## Included capabilities

- One centralized EpiAgent using the configured OpenAI model (by default,
  `gpt-5.6-terra`).
- Local attachment reading for common table, document, and image formats.
- Bounded custom Python analysis with the scientific packages pinned in
  `requirements.txt`: pandas, NumPy, SciPy, statsmodels, lifelines,
  Matplotlib, Seaborn, openpyxl, xlrd, and PyArrow.
- Exact result approval before statistics or figures can be interpreted or
  published.
- Study-neutral agent and analysis capabilities. Scientific evidence and
  participant-database DB-RAG are enabled by an installed study package.

Code execution does not pause for code approval. Analysis outputs are staged
for result approval. Approving a result makes that exact artifact available;
it does not automatically request interpretation or force the workflow to
continue.

Custom Python runs in a restricted local subprocess with resource limits and a
timeout. This is a safety boundary for accidental or model-generated mistakes,
not a security sandbox for hostile code. Run the demo only with files and
requests you trust.

The worker also uses CPU, process-count, file-size, environment, and output
limits on both supported platforms.
Linux retains the 2 GB worker address-space limit.
macOS does not enforce a per-worker address-space ceiling because that
operating-system limit is not supported by the local Python runtime.

## Study package boundary

The agent repository contains no study database, publication indexes, cohort
design, or vector index. The installer validates each prebuilt archive and
places it under the separately configured local `study_data/studies/` registry.
Chat state, uploaded files, and generated datasets remain under `runtime/`.
It does not rebuild
databases, embeddings, or indexes inside the agent repository.

## Branch contents

`working-demo` is the complete development and runnable-demo branch. It keeps
the FastAPI backend, TypeScript frontend source, tests, smoke scripts,
documentation, the study-package installer, and the prebuilt browser bundle
under `frontend/dist`.

`minimal-work` is the separately maintained lightweight participant-delivery
branch. Delivery-only pruning and ignore rules belong there and must not be
merged back into `working-demo`.

## Optional Docker start

Docker is not required, but the same application can be started in a container:

```bash
docker compose up --build
```
