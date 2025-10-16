from typing import Optional
import asyncio
import boto3

from app.core.config import settings


class DynamoRepository:
    """Thin wrapper around DynamoDB using boto3. Blocking I/O is offloaded to a thread."""

    def __init__(self, table_name: Optional[str] = None, region_name: Optional[str] = None):
        self.table_name = table_name or settings.dynamodb_table
        self.region_name = region_name or settings.aws_region
        # boto3 resources/clients are thread-safe for most operations
        self._resource = boto3.resource("dynamodb", region_name=self.region_name)
        self._table = self._resource.Table(self.table_name)

    # --- sync implementations (run in thread) ---
    def _get_item_sync(self, email: str) -> bool:
        resp = self._table.get_item(Key={"email": email.lower()})
        return "Item" in resp and bool(resp["Item"].get("is_premium", False))

    def _put_item_sync(self, email: str, is_premium: bool) -> None:
        self._table.put_item(Item={"email": email.lower(), "is_premium": bool(is_premium)})

    # --- async API ---
    async def is_premium(self, email: str) -> bool:
        return await asyncio.to_thread(self._get_item_sync, email)

    async def put_user(self, email: str, is_premium: bool) -> None:
        await asyncio.to_thread(self._put_item_sync, email, is_premium)
