import json
from uuid import uuid4
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import (get_dynamodb_resource, get_dynamodb_client,)


def process_payment(event):
    event_id = event.get("event_id")
    order_id = event.get("order_id")

    if not event_id:
        raise ValueError("event_id é obrigatório.")

    if not order_id:
        raise ValueError("order_id é obrigatório.")

    dynamodb = get_dynamodb_resource()

    orders_table = dynamodb.Table("Orders")
    processed_table = dynamodb.Table("ProcessedEvents")

    consumer_name = "pagador"
    consumer_event_id = f"{consumer_name}#{event_id}"


    # 1. Verifica se o evento já foi processado
    processed_response = processed_table.get_item(
        Key={"consumer_event_id": consumer_event_id}
    )

    if "Item" in processed_response:
        return {
            "message": "Evento já processado.",
            "status": "PAID",
            "payment_id": processed_response["Item"].get("payment_id")
        }

    # 2. Busca o pedido
    response = orders_table.get_item(
        Key={"order_id": order_id}
    )

    order = response.get("Item")

    if not order:
        raise ValueError("Pedido não encontrado.")

    if order["status"] == "PAID":
        raise ValueError(
            "Pedido já foi pago por outro evento."
        )

    if order["status"] != "RESERVED":
        raise ValueError(
            "Pedido não está disponível para pagamento."
        )

    processed_at = datetime.now(timezone.utc).isoformat()

    # 3. Simula a aprovação do pagamento
    payment_id = str(uuid4())

    paid_event_id = str(uuid4())

    paid_event = {
        "event_id": paid_event_id,
        "event_type": "ORDER_PAID",
        "order_id": order_id,
        "customer_id": order["customer_id"],
        "total_amount": str(order["total_amount"]),
        "payment_id": payment_id,
        "status": "PAID",
        "paid_at": processed_at
    }

    outbox_event = {
        "event_id": paid_event_id,
        "event_type": "ORDER_PAID",
        "payload": json.dumps(paid_event),
        "status": "PENDING",
        "created_at": processed_at
    }

    client = get_dynamodb_client()

    # 4. Atualiza o pedido, registra idempotência
    # e cria o evento ORDER_PAID atomicamente
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
                            "payment_id = :payment_id, "
                            "paid_at = :paid_at"
                        ),
                        "ConditionExpression": "#status = :reserved",
                        "ExpressionAttributeNames": {
                            "#status": "status"
                        },
                        "ExpressionAttributeValues": {
                            ":status": {"S": "PAID"},
                            ":reserved": {"S": "RESERVED"},
                            ":payment_id": {"S": payment_id},
                            ":paid_at": {"S": processed_at}
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
                             "payment_id": {
                                "S": payment_id
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
                                "S": paid_event_id
                            },
                            "event_type": {
                                "S": "ORDER_PAID"
                            },
                            "payload": {
                                "S": json.dumps(paid_event)
                            },
                            "status": {
                                "S": "PENDING"
                            },
                            "created_at": {
                                "S": processed_at
                            }
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(event_id)"
                        )
                    }
                }
            ]
        )

        return {
            "message": "Pagamento processado com sucesso.",
            "status": "PAID",
            "payment_id": payment_id
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
                    "status": "PAID",
                    "payment_id": processed_response["Item"].get("payment_id")
                }

            # 6. Verifica se outro evento pagou o pedido
            latest_order = orders_table.get_item(
                Key={"order_id": order_id}
            ).get("Item")

            if latest_order and latest_order["status"] == "PAID":
                raise ValueError(
                    "Pedido já foi pago por outro evento."
                ) from error

        raise
