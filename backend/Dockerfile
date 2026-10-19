FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-agent.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY .slowapi.env ./
RUN mkdir -p uploads && chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "scripts/docker-entrypoint.sh"]
