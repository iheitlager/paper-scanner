# Builder stage
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
RUN pip install --upgrade pip setuptools wheel && \
    pip install \
    Flask==3.0.0 \
    Flask-CORS==4.0.0 \
    psycopg2-binary==2.9.9 \
    python-dotenv==1.0.0 \
    requests==2.31.0 \
    gunicorn==21.2.0

# Production stage
FROM python:3.11-slim AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application files
COPY --chown=appuser:appuser src/paper_scanner/web/*.py ./
COPY --chown=appuser:appuser src/paper_scanner/web/templates/ ./templates/
COPY --chown=appuser:appuser src/paper_scanner/web/static/ ./static/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "server:app"]
