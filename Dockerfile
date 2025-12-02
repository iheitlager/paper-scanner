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
    Flask==3.1.2 \
    Flask-CORS==6.0.1 \
    psycopg2-binary==2.9.11 \
    python-dotenv==1.2.1 \
    requests==2.32.5 \
    gunicorn==23.0.0

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
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy entire paper_scanner package
COPY --chown=appuser:appuser src/paper_scanner/ ./paper_scanner/
COPY --chown=appuser:appuser src/paper_scanner/web/templates/ ./paper_scanner/web/templates/
COPY --chown=appuser:appuser src/paper_scanner/web/static/ ./paper_scanner/web/static/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "paper_scanner.web.server:app"]
