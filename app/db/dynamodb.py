from typing import Optional
import asyncio
from datetime import datetime, timezone
import boto3

from app.core.config import settings


class DynamoRepository:
    """Thin wrapper around DynamoDB using boto3. Blocking I/O is offloaded to a thread."""

    def __init__(self, table_name: Optional[str] = None, region_name: Optional[str] = None):
        self.table_name = table_name or settings.dynamodb_table
        self.region_name = region_name or settings.aws_region
        # boto3 resources/clients are thread-safe for most operations
        self._resource = boto3.resource("dynamodb", region_name=self.region_name)
        # boto3 uses dynamic attributes; type checkers may not know about Table
        self._table = self._resource.Table(self.table_name)  # type: ignore[attr-defined]

    # --- sync implementations (run in thread) ---
    def _get_item_sync(self, email: str) -> bool:
        resp = self._table.get_item(Key={"email": email.lower()})
        return "Item" in resp and bool(resp["Item"].get("is_premium", False))

    def _exists_sync(self, email: str) -> bool:
        resp = self._table.get_item(Key={"email": email.lower()})
        return "Item" in resp

    def _put_item_sync(self, email: str, is_premium: bool) -> None:
        # Store current UTC date in YYYY-MM-DD format
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._table.put_item(
            Item={
                "email": email.lower(),
                "is_premium": bool(is_premium),
                "timestamp": ts,
            }
        )

    def _put_item_with_timestamp_sync(self, email: str, is_premium: bool, timestamp: str) -> None:
        # Assume timestamp is already a UTC date string YYYY-MM-DD
        self._table.put_item(
            Item={
                "email": email.lower(),
                "is_premium": bool(is_premium),
                "timestamp": timestamp,
            }
        )

    def _update_timestamp_sync(self, email: str, timestamp: str) -> None:
        # Conditionally update timestamp only if the item exists
        self._table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="SET #ts = :ts",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={":ts": timestamp},
            ConditionExpression="attribute_exists(email)",
        )

    # --- async API ---
    async def is_premium(self, email: str) -> bool:
        return await asyncio.to_thread(self._get_item_sync, email)

    async def exists(self, email: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, email)

    async def put_user(self, email: str, is_premium: bool) -> None:
        await asyncio.to_thread(self._put_item_sync, email, is_premium)

    async def put_user_with_timestamp(self, email: str, is_premium: bool, timestamp: str) -> None:
        await asyncio.to_thread(self._put_item_with_timestamp_sync, email, is_premium, timestamp)

    async def update_timestamp(self, email: str, timestamp: str) -> None:
        await asyncio.to_thread(self._update_timestamp_sync, email, timestamp)


def ensure_table_exists(table_name: str, region: str) -> None:
    """Ensure the DynamoDB table exists; create it if missing.

    Idempotent: If the table already exists, returns immediately.
    Blocks until the table is ACTIVE when creating.
    """
    client = boto3.client("dynamodb", region_name=region)
    try:
        resp = client.describe_table(TableName=table_name)
        status = resp.get("Table", {}).get("TableStatus")
        if status != "ACTIVE":
            waiter = client.get_waiter("table_exists")
            waiter.wait(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        # Not found -> try to create
        pass

    try:
        # Create table with partition key 'email' (S) and on-demand billing
        client.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=[{"Key": "app", "Value": "paypal-premium-manager"}],
        )
    except client.exceptions.ResourceInUseException:
        # Another worker/process already initiated creation; just wait
        pass

    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
