# Dockerfile for ECHO Telegram Bot
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ca-certificates \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Configure DNS
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Copy requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Run migrations, collect static files, and start bot
CMD python manage.py migrate && python manage.py collectstatic --noinput && python manage.py run_telegram_bot
