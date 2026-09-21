FROM python:3.12-slim

# Build with --build-arg WITH_H2=true to add Java and the H2 driver.
ARG WITH_H2=false

LABEL org.opencontainers.image.title="SQL2API" \
      org.opencontainers.image.description="Turn SQL into a REST API: run queries against MySQL, PostgreSQL, ClickHouse, SQLite or H2 over HTTP." \
      org.opencontainers.image.source="https://github.com/AnanthaRajuC/SQL2API" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN if [ "$WITH_H2" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends default-jre-headless \
        && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY pyproject.toml README.md ./
COPY sql2api ./sql2api
RUN pip install ".[mysql,postgres,clickhouse,server]" \
    && if [ "$WITH_H2" = "true" ]; then pip install ".[h2]"; fi

RUN useradd --create-home app && mkdir /data && chown app /data
USER app

# db_connections.json and saved_sql/ live here - mount a volume to keep them.
ENV SQL2API_HOME=/data
VOLUME /data
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)"]

# One worker: saved-query and connection files are protected by an in-process lock.
# The worker timeout must stay above SQL2API_QUERY_TIMEOUT (30 s by default), or gunicorn would kill the worker
# at the same moment the database cancels a slow query.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", \
     "--timeout", "120", "--graceful-timeout", "30", "--access-logfile", "-", "sql2api.app:create_app()"]
