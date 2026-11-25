from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
from src.shared.database.dynamodb import get_dynamodb_resource
from src.shared.events.sqs import send_message
from src.shared.config.settings import (SQS_ORDER_CREATED_QUEUE_URL, SQS_ORDER_RESERVED_QUEUE_URL, SQS_ORDER_PAID_QUEUE_URL, SQS_ORDER_INVOICED_QUEUE_URL, SQS_ORDER_REFUNDED_QUEUE_URL, SQS_ORDER_REFUND_REQUESTED_QUEUE_URL,)


def publish_pending_events():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("Outbox")

    queue_urls = {
        "ORDER_CREATED": SQS_ORDER_CREATED_QUEUE_URL,
        "ORDER_RESERVED": SQS_ORDER_RESERVED_QUEUE_URL,
        "ORDER_PAID": SQS_ORDER_PAID_QUEUE_URL,
        "ORDER_INVOICED": SQS_ORDER_INVOICED_QUEUE_URL,
        "ORDER_REFUNDED": SQS_ORDER_REFUNDED_QUEUE_URL,
        "ORDER_REFUND_REQUESTED": SQS_ORDER_REFUND_REQUESTED_QUEUE_URL,
    }

    published_count = 0
    pending_events = []

    # 1. Busca todos os eventos pendentes
    response = table.query(
        IndexName="StatusCreatedAtIndex",
        KeyConditionExpression=Key("status").eq("PENDING")
    )

    pending_events.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="StatusCreatedAtIndex",
            KeyConditionExpression=Key("status").eq("PENDING"),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )

        pending_events.extend(response.get("Items", []))

    # 2. Publica cada evento na fila correspondente
    for event in pending_events:
        try:
            event_type = event["event_type"]

            queue_url = queue_urls.get(event_type)

            if not queue_url:
                print(
                    f"Tipo de evento não suportado: {event_type}"
                )
                continue

            send_message(
                queue_url=queue_url,
                message_body=event["payload"]
            )

            # 3. Atualiza o status após publicação
            table.update_item(
                Key={"event_id": event["event_id"]},
                UpdateExpression=(
                    "SET #status = :status, "
                    "published_at = :published_at"
                ),
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "PUBLISHED",
                    ":published_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }
            )

            published_count += 1

        except Exception as error:
            print(
                f"Erro ao publicar evento "
                f"{event.get('event_id')}: {error}"
            )

    return published_count