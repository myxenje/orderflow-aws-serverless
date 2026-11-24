import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from src.shared.database.dynamodb import transact_write_items


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