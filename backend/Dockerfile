FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv
FROM postgres:18.6-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6 AS pg-tools
# Keep the pinned tools' loader/libs separate from the Bookworm Python runtime.
RUN mkdir -p /tools/lib && cp /usr/lib/postgresql/18/bin/pg_dump /usr/lib/postgresql/18/bin/pg_restore /tools/ && \
    ldd /tools/pg_dump /tools/pg_restore | awk '/=> \/.* / {print $3} /^\s*\/.*ld-linux/ {print $1}' | sort -u | xargs -I '{}' cp -L '{}' /tools/lib/ && \
    cp -L /lib/*/ld-linux-*.so.* /tools/ld.so
FROM python:3.14.9-slim-bookworm@sha256:945c2676dc2b18e0c1f16879244122c57c0ffede60006bf3df159c507a31bcae AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=pg-tools /tools/ /opt/pg-tools/
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CONFIG=1 UV_SYSTEM_CERTS=true UV_LINK_MODE=copy UV_CACHE_DIR=/tmp/uv-cache HOME=/tmp
WORKDIR /app
RUN chown 1000:1000 /app
USER 1000:1000
COPY --chown=1000:1000 pyproject.toml uv.lock ./
RUN --mount=type=cache,id=opengym-platform-uv,target=/tmp/uv-cache,uid=1000,gid=1000 \
    uv lock --check && uv sync --locked --no-install-project && uv pip check && uv lock --check --offline
FROM dependencies AS test-base
COPY --chown=1000:1000 versions.json dependency-licenses.json ./
COPY --chown=1000:1000 src/ ./src/
COPY --chown=1000:1000 tests/ ./tests/
# Windows build contexts may otherwise mark Python source as executable.
RUN find src tests -type f -name '*.py' -exec chmod 0644 {} +
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH

FROM dependencies AS production-deps
RUN --mount=type=cache,id=opengym-platform-uv,target=/tmp/uv-cache,uid=1000,gid=1000 \
    uv sync --locked --no-dev --no-install-project && uv pip check

FROM python:3.14.9-slim-bookworm@sha256:945c2676dc2b18e0c1f16879244122c57c0ffede60006bf3df159c507a31bcae AS runtime
RUN python -m pip uninstall --yes pip
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH HOME=/tmp
WORKDIR /app
COPY --from=production-deps /app/.venv/ /app/.venv/
COPY src/opengym_platform/__init__.py /app/src/opengym_platform/
COPY src/opengym_platform/core/ /app/src/opengym_platform/core/
COPY src/opengym_platform/application.py /app/src/opengym_platform/
USER 1000:1000
ENTRYPOINT ["/app/.venv/bin/python"]
CMD ["-m", "uvicorn", "opengym_platform.application:create_app", "--factory", "--host", "0.0.0.0", "--port", "3000", "--workers", "1", "--no-access-log"]

FROM runtime AS dev
# Uvicorn's stat reloader needs no extra watcher dependency.
CMD ["-m", "uvicorn", "opengym_platform.application:create_app", "--factory", "--host", "0.0.0.0", "--port", "3000", "--reload", "--no-access-log"]

FROM runtime AS migrate
COPY src/opengym_platform/platform_migrate.py /app/src/opengym_platform/
COPY src/opengym_platform/platform_migrations/ /app/src/opengym_platform/platform_migrations/
ENTRYPOINT ["/app/.venv/bin/python", "-m", "opengym_platform.platform_migrate"]
CMD ["--deployment", "up"]

FROM runtime AS ops
COPY --from=pg-tools /tools/ /opt/pg-tools/
COPY --chmod=0555 pg-tool.sh /usr/local/bin/pg_dump
COPY --chmod=0555 pg-tool.sh /usr/local/bin/pg_restore
CMD ["-c", "import subprocess; subprocess.run(['pg_dump', '--version'], check=True)"]

FROM test-base AS test
ENTRYPOINT ["/app/.venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short"]

CMD ["tests"]

# Untargeted builds produce the runtime, not transition tooling.
FROM runtime AS default
