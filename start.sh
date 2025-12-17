#!/bin/bash
# Startup script for Render (free tier)
# Runs migrations before starting the server

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn server..."
gunicorn firstbackend.wsgi --bind 0.0.0.0:$PORT

