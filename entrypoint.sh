#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
python manage.py migrate --check --noinput || python manage.py migrate

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start gunicorn
exec gunicorn scholarship.wsgi:application --bind 0.0.0.0:8000 --timeout 120 --workers 4
