#!/usr/bin/env python3
"""
Backfill 'timestamp' attribute for items that miss it.

- Writes 'timestamp' in UTC as YYYY-MM-DD
- Uses conditional update to avoid overwriting if already present

Usage:
  python scripts/backfill_timestamp.py --table <TABLE_NAME> --region <AWS_REGION>

Env vars respected (fallbacks to app config if you import it):
  AWS_REGION, DYNAMODB_TABLE
"""
import argparse
from datetime import datetime, timezone
import time
import boto3
from botocore.exceptions import ClientError


def backfill(table_name: str, region: str, dry_run: bool = False) -> None:
    dynamo = boto3.resource("dynamodb", region_name=region)
    table = dynamo.Table(table_name)  # type: ignore[attr-defined]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scanned = 0
    updated = 0

    params = {
        "ProjectionExpression": "#e, is_premium, #ts",
        "ExpressionAttributeNames": {"#e": "email", "#ts": "timestamp"},
    }

    resp = table.scan(**params)
    while True:
        items = resp.get("Items", [])
        scanned += len(items)
        for it in items:
            if "timestamp" in it and isinstance(it["timestamp"], str) and len(it["timestamp"]) == 10:
                continue
            email = it["email"].lower()
            if dry_run:
                print(f"Would update {email} -> timestamp={today}")
                updated += 1
                continue
            try:
                table.update_item(
                    Key={"email": email},
                    UpdateExpression="SET #ts = :ts",
                    ExpressionAttributeNames={"#ts": "timestamp"},
                    ExpressionAttributeValues={":ts": today},
                    ConditionExpression="attribute_not_exists(#ts)",
                )
                updated += 1
            except ClientError as e:
                if e.response["Error"].get("Code") == "ConditionalCheckFailedException":
                    # Someone already set it between scan and update
                    continue
                raise
        if "LastEvaluatedKey" not in resp:
            break
        # simple pacing to avoid throttling in large tables
        time.sleep(0.1)
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **params)

    print(f"Scanned: {scanned}, Updated: {updated}, Date used: {today}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backfill(args.table, args.region, args.dry_run)
