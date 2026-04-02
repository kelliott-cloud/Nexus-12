FROM python:3.11-slim AS backend-build
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

# Install Playwright system dependencies + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libx11-xcb1 libxcb1 libx11-6 \
    fonts-liberation fonts-noto-color-emoji \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-build /usr/local/bin /usr/local/bin

# Install Playwright Firefox browser
RUN python -m playwright install firefox

COPY backend/ /app/backend/

EXPOSE 8080

# Cloud Run ignores Docker HEALTHCHECK — configure startup/liveness probes
# in the Cloud Run service definition instead (see cloudrun.yaml).
WORKDIR /app/backend

# Force WORKERS=1 to prevent duplicate background tasks, state divergence,
# and Pub/Sub subscriber conflicts. Cloud Run scales horizontally via
# instances, not via in-process workers.
ENV WORKERS=1
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WORKERS:-1}"]
