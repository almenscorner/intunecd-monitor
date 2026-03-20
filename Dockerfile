# ── Base image ────────────────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.12-slim-bookworm AS base

WORKDIR /intunecd

# System dependencies (git only — no ODBC/SQL Server drivers needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configure git
RUN git config --global user.email "intunecd-monitor@intunecd.local" \
 && git config --global user.name "IntuneCD Monitor"

# Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip --quiet \
 && pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN useradd -m -u 1000 appuser

# ── Web server image ──────────────────────────────────────────────────────────
FROM base AS web

COPY . /intunecd
RUN mkdir -p /intunecd/db /documentation /intunecd/git \
 && chown -R appuser:appuser /intunecd /documentation

RUN chmod u+x ./server-entrypoint.sh

USER appuser

ENTRYPOINT ["/bin/bash", "-c", "./server-entrypoint.sh"]
