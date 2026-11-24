import json
from uuid import uuid4
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import (get_dynamodb_resource, get_dynamodb_client,)


def reserve_order(event):
    event_id = event.get("event_id")
    order_id = event.get("order_id")

    if not event_id:
        raise ValueError("event_id é obrigatório.")

    if not order_id:
        raise ValueError("order_id é obrigatório.")

    dynamodb = get_dynamodb_resource()

    orders_table = dynamodb.Table("Orders")
    processed_table = dynamodb.Table("ProcessedEvents")

    consumer_name = "reservador"
    consumer_event_id = f"{consumer_name}#{event_id}"

    # 1. Verifica se o evento foi processado
    processed_response = processed_table.get_item(
        Key={"consumer_event_id": consumer_event_id}
    )

    if "Item" in processed_response:
        return {
            "message": "Evento já processado.",
            "status": "RESERVED"
        }

    # 2. Busca pedido
    response = orders_table.get_item(
        Key={"order_id": order_id}
    )

    order = response.get("Item")

    if not order:
        raise ValueError("Pedido não encontrado.")

    if order["status"] == "RESERVED":
        raise ValueError(
            "Pedido já foi reservado por outro evento."
        )

    if order["status"] != "PENDING":
        raise ValueError(
            "Pedido não está disponível para reserva."
        )

    processed_at = datetime.now(timezone.utc).isoformat()

    # 3. Prepara evento ORDERRESERVED
    reserved_event_id = str(uuid4())

    reserved_event = {
        "event_id": reserved_event_id,
        "event_type": "ORDER_RESERVED",
        "order_id": order_id,
        "customer_id": order["customer_id"],
        "total_amount": str(order["total_amount"]),
        "status": "RESERVED",
        "reserved_at": processed_at
    }

    outbox_event = {
        "event_id": reserved_event_id,
        "event_type": "ORDER_RESERVED",
        "payload": json.dumps(reserved_event),
        "status": "PENDING",
        "created_at": processed_at
    }

    client = get_dynamodb_client()

    # 4. Reserva pedido e registra o evento 
    try:
        client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": "Orders",
                        "Key": {
                            "order_id": {"S": order_id}
                        },
                        "UpdateExpression": (
                            "SET #status = :status, "
                            "reserved_at = :reserved_at"
                        ),
                        "ConditionExpression": "#status = :pending",
                        "ExpressionAttributeNames": {
                            "#status": "status"
                        },
                        "ExpressionAttributeValues": {
                            ":status": {"S": "RESERVED"},
                            ":pending": {"S": "PENDING"},
                            ":reserved_at": {"S": processed_at}
                        }
                    }
                },
                {
                    "Put": {
                        "TableName": "ProcessedEvents",
                        "Item": {
                            "consumer_event_id": {
                                "S": consumer_event_id
                            },
                            "consumer_name": {
                                "S": consumer_name
                            },
                            "event_id": {
                                "S": event_id
                            },
                            "processed_at": {
                                "S": processed_at
                            }
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(consumer_event_id)"
                        )
                    }
                },
                {
                    "Put": {
                        "TableName": "Outbox",
                        "Item": {
                            "event_id": {
                                "S": outbox_event["event_id"]
                            },
                            "event_type": {
                                "S": outbox_event["event_type"]
                            },
                            "payload": {
                                "S": outbox_event["payload"]
                            },
                            "status": {
                                "S": outbox_event["status"]
                            },
                            "created_at": {
                                "S": outbox_event["created_at"]
                            }
                        },
                        "ConditionExpression": "attribute_not_exists(event_id)"
                    }
                }
            ]
        )

        return {
            "message": "Pedido reservado com sucesso.",
            "status": "RESERVED"
        }

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "TransactionCanceledException":

            # 5. Verifica se outra execução processou o mesmo evento
            processed_response = processed_table.get_item(
                Key={"consumer_event_id": consumer_event_id}
            )

            if "Item" in processed_response:
                return {
                    "message": "Evento já processado.",
                    "status": "RESERVED"
                }

            # 6. Verifica se outro evento reservou o pedido
            latest_order = orders_table.get_item(
                Key={"order_id": order_id}
            ).get("Item")

            if latest_order and latest_order["status"] == "RESERVED":
                raise ValueError(
                    "Pedido já foi reservado por outro evento."
                ) from error

        raise