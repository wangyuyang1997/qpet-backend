# Q宠乐斗 v5.0 后端
# 多阶段构建：builder 装依赖 → runtime 只拷贝 venv + 代码
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .

# 装依赖到 venv
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -e ".[dev]" 2>/dev/null || \
    /opt/venv/bin/pip install --no-cache-dir \
        "fastapi[standard]>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "sqlalchemy[asyncio]>=2.0.0" \
        "asyncpg>=0.30.0" \
        "alembic>=1.14.0" \
        "apscheduler>=3.10.0" \
        "redis>=5.2.0" \
        "pika>=1.3.0" \
        "aio-pika>=9.5.0" \
        "python-jose[cryptography]>=3.3.0" \
        "passlib[bcrypt]>=1.7.4" \
        "pydantic>=2.0.0" \
        "pydantic-settings>=2.0.0" \
        "sse-starlette>=2.0.0" \
        "cryptography>=43.0.0" \
        "httpx>=0.28.0" \
        "python-multipart>=0.0.12" \
        "structlog>=24.0.0"

# —— runtime ——
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r qpet && useradd -r -g qpet qpet

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

RUN chown -R qpet:qpet /app
USER qpet

EXPOSE 3456
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -sf http://localhost:3456/api/version || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3456"]
