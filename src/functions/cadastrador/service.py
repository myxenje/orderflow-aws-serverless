import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import (transact_write_items, get_dynamodb_resource)


def create_order(order_data):
    customer_id = order_data.get("customer_id")
    items = order_data.get("items")

    # Validação dados do pedido
    if not customer_id or not isinstance(customer_id, str):
        raise ValueError("customer_id é obrigatório.")

    if not isinstance(items, list) or not items:
        raise ValueError("O pedido precisa conter pelo menos um produto.")

    total_amount = Decimal("0")
    processed_items = []

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Cada item do pedido deve ser um objeto.")

        product_id = item.get("product_id")
        quantity = item.get("quantity")
        unit_price = item.get("unit_price")

        if not product_id:
            raise ValueError("product_id é obrigatório.")

        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity deve ser um número inteiro positivo.")

        try:
            unit_price = Decimal(str(unit_price))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("unit_price deve ser um valor numérico válido.")

        if not unit_price.is_finite() or unit_price <= 0:
            raise ValueError("unit_price deve ser maior que zero.")

        subtotal = unit_price * quantity
        total_amount += subtotal

        processed_items.append({
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal
        })

    # Montagem Pedido
    order_id = str(uuid4())
    event_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    order = {
        "order_id": order_id,
        "customer_id": customer_id,
        "items": processed_items,
        "total_amount": total_amount,
        "status": "PENDING",
        "created_at": created_at
    }

    # Montagem evento
    message = {
        "event_id": event_id,
        "event_type": "ORDER_CREATED",
        "order_id": order_id,
        "customer_id": customer_id,
        "total_amount": str(total_amount),
        "status": "PENDING",
        "created_at": created_at
    }

    outbox_event = {
        "event_id": event_id,
        "event_type": "ORDER_CREATED",
        "payload": json.dumps(message),
        "status": "PENDING",
        "created_at": created_at
    }

    # Persistência atômica do pedido e do evento
    transact_write_items([
        {
            "table_name": "Orders",
            "item": order
        },
        {
            "table_name": "Outbox",
            "item": outbox_event
        }
    ])

    return order

def request_refund(order_id):
    if not order_id or not isinstance(order_id, str):
        raise ValueError("order_id é obrigatório.")

    dynamodb = get_dynamodb_resource()
    orders_table = dynamodb.Table("Orders")

    response = orders_table.get_item(
        Key={"order_id": order_id}
    )

    order = response.get("Item")

    if not order:
        raise ValueError("Pedido não encontrado.")

    if order.get("status") != "PAID":
        raise ValueError("Somente pedidos pagos podem ser estornados.")

    payment_id = order.get("payment_id")

    if not payment_id:
        raise ValueError("Pedido não possui payment_id.")

    event_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    message = {
        "event_id": event_id,
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order_id,
        "customer_id": order["customer_id"],
        "payment_id": payment_id,
        "total_amount": str(order["total_amount"]),
        "status": "PENDING",
        "created_at": created_at
    }

    outbox_event = {
        "event_id": event_id,
        "event_type": "ORDER_REFUND_REQUESTED",
        "payload": json.dumps(message),
        "status": "PENDING",
        "created_at": created_at
    }

    try:
        transact_write_items([
            {
                "operation": "update",
                "table_name": "Orders",
                "key": {
                    "order_id": order_id
                },
                "update_expression": "SET refund_status = :requested",
                "condition_expression": (
                    "#status = :paid AND attribute_not_exists(refund_status)"
                ),
                "expression_attribute_names": {
                    "#status": "status"
                },
                "expression_attribute_values": {
                    ":requested": "REQUESTED",
                    ":paid": "PAID"
                }
            },
            {
                "table_name": "Outbox",
                "item": outbox_event,
                "condition_expression": "attribute_not_exists(event_id)"
            }
        ])

    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")

        if error_code == "TransactionCanceledException":
            raise ValueError(
                "Já existe uma solicitação de estorno para este pedido."
            ) from error

        raise
    return message