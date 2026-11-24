import boto3

from boto3.dynamodb.types import TypeSerializer
from src.shared.config.settings import (
    AWS_REGION,
    DYNAMODB_ENDPOINT,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
)


def get_dynamodb_resource():
    return boto3.resource(
        "dynamodb",
        region_name=AWS_REGION,
        endpoint_url=DYNAMODB_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def get_dynamodb_client():
    return boto3.client(
        "dynamodb",
        region_name=AWS_REGION,
        endpoint_url=DYNAMODB_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def transact_write_items(items):
    dynamodb = get_dynamodb_client()
    serializer = TypeSerializer()

    serialized_items = []

    for item in items:
        serialized_items.append({
            "Put": {
                "TableName": item["table_name"],
                "Item": {
                    key: serializer.serialize(value)
                    for key, value in item["item"].items()
                }
            }
        })

    dynamodb.transact_write_items(
        TransactItems=serialized_items
    )
