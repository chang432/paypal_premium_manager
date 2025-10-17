# PayPal Premium Manager

A minimal FastAPI service that verifies whether a user email is a premium subscriber. It uses:
- FastAPI for the API
- Redis for hot cache
- AWS DynamoDB for source of truth
- docker-compose to run alongside Redis
- Includes PayPal integration via REST API (OAuth token refresh and hourly transaction fetch)

Intended to run on a Hetzner VPS. The API is meant for internal server-to-server calls (protectable by an internal API key).

## API

- POST `/v1/premium/check`
  - Request: `{ "email": "user@example.com" }`
  - Response: `{ "email": "user@example.com", "premium": true, "source": "cache|db" }`

- GET `/v1/health` health check.

## Configuration

Copy `.env.example` to `.env` and adjust as needed.

Important variables:
- `REDIS_URL` redis connection URL
- `AWS_REGION` and `DYNAMODB_TABLE` for DynamoDB
- AWS credentials via shared config using `AWS_PROFILE` (default `default`). The container mounts your `~/.aws` directory read-only and sets `AWS_SDK_LOAD_CONFIG=1` for profile/SSO support.
- PayPal: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_URL` (sandbox default)

## DynamoDB Table

The service expects a table with:
- Partition key: `email` (String)
- Attribute: `is_premium` (Boolean)

Create it and optionally seed a user:

```bash
# Using host Python and AWS profile
AWS_PROFILE=default python3 scripts/create_table.py --table paypal_premium_users --region us-east-1 --seed-email you@example.com --seed-premium

# Or inside the container (profile and ~/.aws are mounted by compose):
docker compose exec -e AWS_PROFILE=default api python scripts/create_table.py --table paypal_premium_users --region us-east-1 --seed-email you@example.com --seed-premium
```

Minimal IAM policy for the app principal:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DescribeTable"
      ],
  "Resource": "arn:aws:dynamodb:<region>:<account-id>:table/paypal_premium_users"
    }
  ]
}
```

## Run locally

- With Docker (recommended):

```bash
cp .env.example .env
# edit .env to set AWS_PROFILE if not 'default'
docker compose up --build -d
```

Call the API:
## PayPal integration

This image can optionally pull PayPal transactions using the REST API.

1. Set in `.env`:
  - `PAYPAL_CLIENT_ID`
  - `PAYPAL_CLIENT_SECRET`
  - `PAYPAL_BASE_URL` (sandbox default `https://api-m.sandbox.paypal.com`; live is `https://api-m.paypal.com`)

2. The container runs two cron tasks:
  - Every 25 minutes: refresh OAuth token (`scripts/paypal_refresh_token.py`).
  - Hourly: fetch previous hour’s transactions and print a simplified list (`scripts/paypal_fetch_hourly_transactions.py`).

View logs:

```bash
docker compose logs -f api | grep PayPal -n || true
```

Run once manually for testing:

```bash
docker compose exec api python /app/scripts/paypal_refresh_token.py
docker compose exec api python /app/scripts/paypal_fetch_hourly_transactions.py
```

```bash
curl -s -X POST http://localhost:8080/v1/premium/check \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}' | jq
```

- Without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## HTTPS/TLS with Uvicorn directly

This stack can terminate TLS inside the API container if you prefer not to use a reverse proxy.

- Place your certificate and key files at `./certs/cert.pem` and `./certs/key.pem` (or override with `SSL_CERTFILE` and `SSL_KEYFILE`).
- Set `ENABLE_TLS=1` in `.env`.
- Compose exposes both `8080` (HTTP) and `8443` (HTTPS). If `ENABLE_TLS=1` and certs exist, HTTPS will be served on 8443.

Example curl:

```bash
curl -k https://localhost:8443/v1/health
```

Note: Using a reverse proxy (Caddy/Traefik/Nginx) or cloud LB is still recommended for automatic cert management and additional protections.

## Deployment (Hetzner VPS)

1. Install Docker and docker-compose plugin on the VPS.
2. Copy the repo to the VPS and set environment variables (or `.env` file). Do not commit secrets.
3. Run `docker compose up -d --build`.
4. If exposing directly, set up TLS as above and open only port 8443; otherwise place behind a reverse proxy and close direct access.

Note: Ensure your VPS user has `~/.aws/{config,credentials}` populated for the profile you set in `.env` (e.g., `AWS_PROFILE=prod`). The compose file mounts this directory into the container at `/home/appuser/.aws` in read-only mode.

Optional hardening:
- Use Hetzner firewall to only allow port 8080 from your backend's IPs.
- Terminate TLS at a reverse proxy (Caddy/Traefik) if exposing externally.

## Notes

- Caching: Redis keys `premium:<email>` store `"1"`/`"0"` with TTL.
- Consistency: Writes to DynamoDB will update cache on the next read; you can extend with webhook ingestion from PayPal/webhooks to set `is_premium`.
- Observability: Extend with logging and metrics; currently uses defaults.
