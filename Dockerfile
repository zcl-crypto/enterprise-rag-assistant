FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ARG TORCH_VERSION=2.14.0
ARG TORCHVISION_VERSION=0.29.0
COPY pyproject.toml ./
RUN mkdir rag_app && touch rag_app/__init__.py \
    && pip install --index-url https://download.pytorch.org/whl/cpu \
    "torch==${TORCH_VERSION}+cpu" "torchvision==${TORCHVISION_VERSION}+cpu" \
    && pip install -e ".[parsing,postgres,retrieval,model-download,generation]" \
    && rm -rf rag_app

COPY README.md alembic.ini ./
COPY migrations ./migrations
COPY rag_app ./rag_app
COPY scripts ./scripts
COPY reports ./reports

CMD ["python", "-m", "uvicorn", "rag_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
