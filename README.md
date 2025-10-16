# Ko-fi Premium Manager

A minimal FastAPI service that verifies whether a user email is a premium subscriber. It uses:
- FastAPI for the API
- Redis for hot cache
- AWS DynamoDB for source of truth
- docker-compose to run alongside Redis

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

## DynamoDB Table

The service expects a table with:
- Partition key: `email` (String)
- Attribute: `is_premium` (Boolean)

Create it and optionally seed a user:

```bash
# Using host Python and AWS profile
AWS_PROFILE=default python3 scripts/create_table.py --table kofi_premium_users --region us-east-1 --seed-email you@example.com --seed-premium

# Or inside the container (profile and ~/.aws are mounted by compose):
docker compose exec -e AWS_PROFILE=default api python scripts/create_table.py --table kofi_premium_users --region us-east-1 --seed-email you@example.com --seed-premium
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
      "Resource": "arn:aws:dynamodb:<region>:<account-id>:table/kofi_premium_users"
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

## Deployment (Hetzner VPS)

1. Install Docker and docker-compose plugin on the VPS.
2. Copy the repo to the VPS and set environment variables (or `.env` file). Do not commit secrets.
3. Run `docker compose up -d --build`.
4. Put the API behind an internal network, WireGuard, or restrict by firewall. Only allow your webapp backend to call it if needed.

Note: Ensure your VPS user has `~/.aws/{config,credentials}` populated for the profile you set in `.env` (e.g., `AWS_PROFILE=prod`). The compose file mounts this directory into the container at `/home/appuser/.aws` in read-only mode.

Optional hardening:
- Use Hetzner firewall to only allow port 8080 from your backend's IPs.
- Terminate TLS at a reverse proxy (Caddy/Traefik) if exposing externally.

## Notes

- Caching: Redis keys `premium:<email>` store `"1"`/`"0"` with TTL.
- Consistency: Writes to DynamoDB will update cache on the next read; you can extend with webhook ingestion from Ko-fi to set `is_premium`.
- Observability: Extend with logging and metrics; currently uses defaults.
