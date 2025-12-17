@echo off
REM Startup script for Windows (local testing)
REM For Render, use start.sh

echo Running database migrations...
python manage.py migrate --noinput

echo Starting Gunicorn server...
gunicorn firstbackend.wsgi --bind 0.0.0.0:8000

