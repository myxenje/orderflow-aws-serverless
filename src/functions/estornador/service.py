import json
from uuid import uuid4
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from decimal import Decimal
from src.shared.database.dynamodb import (get_dynamodb_resource, get_dynamodb_client,)

def process_refund(event):
    event_id = event.get("event_id")
    order_id = event.get("order_id")
    payment_id = event.get("payment_id")
    event_type = event.get("event_type")

    if not event_id:
        raise ValueError("event_id é obrigatório.")

    if not order_id:
        raise ValueError("order_id é obrigatório.")

    if not payment_id:
        raise ValueError("payment_id é obrigatório.")

    if event_type != "ORDER_REFUND_REQUESTED":
        raise ValueError(
            "O evento deve ser do tipo ORDER_REFUND_REQUESTED."
        )

    dynamodb = get_dynamodb_resource()

    orders_table = dynamodb.Table("Orders")
    processed_table = dynamodb.Table("ProcessedEvents")

    consumer_name = "estornador"
    consumer_event_id = f"{consumer_name}#{event_id}"

    processed_response = processed_table.get_item(
        Key={"consumer_event_id": consumer_event_id}
    )

    if "Item" in processed_response:
        return {
            "message": "Evento já processado.",
            "status": "REFUNDED",
            "payment_id": processed_response["Item"].get("payment_id")
        }

    response = orders_table.get_item(
        Key={"order_id": order_id}
    )

    order = response.get("Item")

    if not order:
        raise ValueError("Pedido não encontrado.")

    if order["status"] == "REFUNDED":
        raise ValueError(
            "Pedido já foi estornado por outro evento."
        )

    if order["status"] != "PAID":
        raise ValueError(
            "Pedido não está disponível para estorno."
        )

    if order.get("payment_id") != payment_id:
        raise ValueError(
            "O payment_id informado não corresponde ao pagamento do pedido."
        )

    items = order.get("items")

    if not isinstance(items, list) or not items:
        raise ValueError("Pedido não possui produtos válidos.")

    stock_quantities = {}

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Item do pedido inválido.")

        product_id = item.get("product_id")
        quantity = item.get("quantity")

        if not isinstance(product_id, str) or not product_id:
            raise ValueError("product_id inválido.")

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, Decimal))
            or quantity <= 0
            or quantity % 1 != 0
        ):
            raise ValueError(
                f"Quantidade inválida para o produto {product_id}."
            )

        quantity = int(quantity)

        stock_quantities[product_id] = (
            stock_quantities.get(product_id, 0) + quantity
        )

    processed_at = datetime.now(timezone.utc).isoformat()

    refunded_event_id = str(uuid4())

    refunded_event = {
        "event_id": refunded_event_id,
        "event_type": "ORDER_REFUNDED",
        "order_id": order_id,
        "customer_id": order["customer_id"],
        "total_amount": str(order["total_amount"]),
        "payment_id": payment_id,
        "status": "REFUNDED",
        "refunded_at": processed_at
    }

    outbox_event = {
        "event_id": refunded_event_id,
        "event_type": "ORDER_REFUNDED",
        "payload": json.dumps(refunded_event),
        "status": "PENDING",
        "created_at": processed_at
    }

    stock_updates = []

    for product_id, quantity in stock_quantities.items():
        stock_updates.append({
            "Update": {
                "TableName": "Stock",
                "Key": {
                    "product_id": {"S": product_id}
                },
                "UpdateExpression": (
                    "SET #quantity = #quantity + :quantity"
                ),
                "ConditionExpression": (
                    "attribute_exists(product_id) "
                    "AND attribute_exists(#quantity)"
                ),
                "ExpressionAttributeNames": {
                    "#quantity": "quantity"
                },
                "ExpressionAttributeValues": {
                    ":quantity": {"N": str(quantity)}
                }
            }
        })

    client = get_dynamodb_client()

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
                            "refunded_at = :refunded_at"
                        ),
                        "ConditionExpression": (
                            "#status = :paid AND payment_id = :payment_id"
                        ),
                        "ExpressionAttributeNames": {
                            "#status": "status"
                        },
                        "ExpressionAttributeValues": {
                            ":status": {"S": "REFUNDED"},
                            ":paid": {"S": "PAID"},
                            ":payment_id": {"S": payment_id},
                            ":refunded_at": {"S": processed_at}
                        }
                    }
                },
                *stock_updates,
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
                                "S": refunded_event_id
                            },
                            "event_type": {
                                "S": "ORDER_REFUNDED"
                            },
                            "payload": {
                                "S": json.dumps(refunded_event)
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
            "message": "Estorno processado com sucesso.",
            "status": "REFUNDED",
            "payment_id": payment_id
        }

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "TransactionCanceledException":

            processed_response = processed_table.get_item(
                Key={"consumer_event_id": consumer_event_id}
            )

            if "Item" in processed_response:
                return {
                    "message": "Evento já processado.",
                    "status": "REFUNDED",
                    "payment_id": processed_response["Item"].get("payment_id")
                }

            latest_order = orders_table.get_item(
                Key={"order_id": order_id}
            ).get("Item")

            if latest_order and latest_order["status"] == "REFUNDED":
                raise ValueError(
                    "Pedido já foi estornado por outro evento."
                ) from error

        raise