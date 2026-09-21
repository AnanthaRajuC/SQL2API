FROM python:3.12-slim

# Build with --build-arg WITH_H2=true to add Java and the H2 driver.
ARG WITH_H2=false

RUN if [ "$WITH_H2" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends default-jre-headless \
        && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY pyproject.toml README.md ./
COPY sql2api ./sql2api
RUN pip install --no-cache-dir ".[mysql,postgres,clickhouse,server]" \
    && if [ "$WITH_H2" = "true" ]; then pip install --no-cache-dir ".[h2]"; fi

RUN useradd --create-home app && mkdir /data && chown app /data
USER app

# db_connections.json and saved_sql/ live here - mount a volume to keep them.
ENV SQL2API_HOME=/data
VOLUME /data
EXPOSE 5000

# One worker: saved-query and connection files are protected by an in-process lock.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "sql2api.app:create_app()"]
