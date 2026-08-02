FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV REPORT_AGENT_STATIC_DIR=/app/frontend/dist
ENV REPORT_AGENT_RUNTIME_ROOT=/app/runtime
ENV REPORT_AGENT_CHECKPOINT_DB_PATH=/app/runtime/agent_memory_fastapi.db

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY config ./config
COPY db_rag ./db_rag
COPY epi_agent ./epi_agent
COPY graph ./graph
COPY study_package ./study_package
COPY tools ./tools
COPY utils ./utils
COPY frontend/dist ./frontend/dist
COPY llm_vllm.py run_fastapi.py study_installer.py ./

RUN mkdir -p /app/runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["python", "run_fastapi.py", "--host", "0.0.0.0", "--port", "8000"]
