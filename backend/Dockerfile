# Multi-stage Dockerfile for SangamMW backend
# Stage 1: builder — installs all dependencies
# Stage 2: production — minimal runtime image

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --upgrade pip \
    && pip install --prefix=/install hatch \
    && pip install --prefix=/install -e ".[all-connectors]"


FROM python:3.11-slim AS production

LABEL org.opencontainers.image.source="https://github.com/sangamai/sangam-mw"
LABEL org.opencontainers.image.description="SangamMW — Open-source iPaaS platform"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN pip install -e . --no-deps

RUN useradd -r -s /bin/false sangam
USER sangam

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "sangam_mw.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
