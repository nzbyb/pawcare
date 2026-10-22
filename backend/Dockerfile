FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 国内服务器可用构建参数换成镜像源：
#   docker compose build --build-arg APT_MIRROR=mirrors.aliyun.com \
#                        --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG APT_MIRROR=
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|$APT_MIRROR|g; s|security.debian.org|$APT_MIRROR|g" \
        /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-agent.txt ./
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY .slowapi.env ./
RUN mkdir -p uploads && chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "scripts/docker-entrypoint.sh"]
