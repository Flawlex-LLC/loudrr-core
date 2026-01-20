FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=echo.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy project
COPY . .

# Collect static files (will be served by whitenoise)
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command - production with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "120", "echo.wsgi:application"]
