import boto3
from boto3.dynamodb.types import TypeSerializer
from src.shared.config.settings import (AWS_REGION, DYNAMODB_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,)


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
        operation = item.get("operation", "put")

        expression_values = {
            key: serializer.serialize(value)
            for key, value in item.get(
                "expression_attribute_values", {}
            ).items()
        }

        if operation == "update":
            update_operation = {
                "TableName": item["table_name"],
                "Key": {
                    key: serializer.serialize(value)
                    for key, value in item["key"].items()
                },
                "UpdateExpression": item["update_expression"]
            }

            if "condition_expression" in item:
                update_operation["ConditionExpression"] = (
                    item["condition_expression"]
                )

            if expression_values:
                update_operation["ExpressionAttributeValues"] = expression_values

            if "expression_attribute_names" in item:
                update_operation["ExpressionAttributeNames"] = (
                    item["expression_attribute_names"]
                )

            serialized_items.append({"Update": update_operation})

        else:
            put_operation = {
                "TableName": item["table_name"],
                "Item": {
                    key: serializer.serialize(value)
                    for key, value in item["item"].items()
                }
            }

            if "condition_expression" in item:
                put_operation["ConditionExpression"] = (
                    item["condition_expression"]
                )

            if expression_values:
                put_operation["ExpressionAttributeValues"] = expression_values

            if "expression_attribute_names" in item:
                put_operation["ExpressionAttributeNames"] = (
                    item["expression_attribute_names"]
                )

            serialized_items.append({"Put": put_operation})

    dynamodb.transact_write_items(TransactItems=serialized_items)