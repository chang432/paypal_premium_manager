# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl cron && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY entrypoint.sh /app/entrypoint.sh
COPY scripts /app/scripts
RUN chmod +x /app/scripts/*.py || true

EXPOSE 8080 8443

# Non-root user
RUN useradd -ms /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /app/entrypoint.sh
USER root

CMD sh -c 'echo "*/25 * * * * appuser export PYTHONPATH=/app && /usr/local/bin/python /app/scripts/paypal_refresh_token.py >> /proc/1/fd/1 2>&1" > /etc/cron.d/appcron && \
           echo "0 * * * * appuser export PYTHONPATH=/app && /usr/local/bin/python /app/scripts/paypal_fetch_hourly_transactions.py >> /proc/1/fd/1 2>&1" >> /etc/cron.d/appcron && \
           chmod 0644 /etc/cron.d/appcron && \
           crontab -u appuser /etc/cron.d/appcron && \
           service cron start && \
           /app/entrypoint.sh'
