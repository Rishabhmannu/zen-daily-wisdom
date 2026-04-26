FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV BACKEND_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "zen_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

