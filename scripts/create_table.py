#!/usr/bin/env python3
import argparse
import boto3


def ensure_table(table_name: str, region: str):
    dynamodb = boto3.client("dynamodb", region_name=region)
    existing = dynamodb.list_tables()["TableNames"]
    if table_name in existing:
        print(f"Table {table_name} already exists")
        return
    print(f"Creating table {table_name} ...")
    dynamodb.create_table(
        TableName=table_name,
        AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
        Tags=[{"Key": "app", "Value": "paypal-premium-manager"}],
    )
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print("Table is ready.")


def seed_user(table_name: str, region: str, email: str, premium: bool):
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    table.put_item(Item={"email": email.lower(), "is_premium": premium})
    print(f"Seeded {email} -> {premium}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default="paypal_premium_users")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--seed-email", default=None)
    parser.add_argument("--seed-premium", action="store_true")
    args = parser.parse_args()

    ensure_table(args.table, args.region)
    if args.seed_email:
        seed_user(args.table, args.region, args.seed_email, args.seed_premium)
