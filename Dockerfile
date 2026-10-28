# syntax=docker/dockerfile:1.7
# Multi-stage build: wheel + dependencies in a venv, then a slim non-root runtime.
FROM python:3.13-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

FROM python:3.13-slim AS runtime
LABEL org.opencontainers.image.title="vigil" \
      org.opencontainers.image.description="Scam interception, mule-network investigation and AI-agent payment safety" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin vigil
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request as u; u.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/healthz', timeout=2)"
CMD ["vigil-serve"]
