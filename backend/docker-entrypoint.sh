#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting application..."

# Check if RUN_MODE is set to "bot" to run Telegram bot instead of gunicorn
if [ "$RUN_MODE" = "bot" ]; then
    echo "Starting Telegram bot..."
    exec python manage.py run_telegram_bot
else
    exec "$@"
fi
