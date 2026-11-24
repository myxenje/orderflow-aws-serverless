from datetime import datetime, timezone
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import get_dynamodb_resource


def mark_event_as_processed(consumer_name, event_id):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("ProcessedEvents")

    consumer_event_id = f"{consumer_name}#{event_id}"

    try:
        table.put_item(
            Item={
                "consumer_event_id": consumer_event_id,
                "consumer_name": consumer_name,
                "event_id": event_id,
                "processed_at": datetime.now(timezone.utc).isoformat()
            },
            ConditionExpression="attribute_not_exists(consumer_event_id)"
        )

        return True

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            return False

        raise