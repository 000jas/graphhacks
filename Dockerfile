# =============================================================================
# GraphOS — Evidence-Bound Graph Intelligence Agent Container
# =============================================================================
FROM python:3.11-slim AS base

# Environment configurations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/home/graphos/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN useradd -m -u 1000 -s /bin/bash graphos

WORKDIR /app

# Install Python dependencies first for caching efficiency
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=graphos:graphos pyproject.toml .
COPY --chown=graphos:graphos graphos .
COPY --chown=graphos:graphos agent/ agent/
COPY --chown=graphos:graphos mcp_server/ mcp_server/
COPY --chown=graphos:graphos dashboard/ dashboard/

# Install editable package and set permissions
RUN pip install --no-cache-dir -e . && chmod +x /app/graphos

# Switch to non-root user
USER graphos

# Expose default dashboard port
EXPOSE 8501

# Default entrypoint: GraphOS CLI
ENTRYPOINT ["python", "-m", "agent"]
CMD []
