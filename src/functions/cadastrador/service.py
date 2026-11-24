import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from src.shared.config.settings import SQS_QUEUE_URL
from src.shared.database.dynamodb import get_dynamodb_resource
from src.shared.events.sqs import send_message


def create_order(order_data):
    customer_id = order_data.get("customer_id")
    items = order_data.get("items")

    # Validação dos dados do pedido
    if not customer_id or not isinstance(customer_id, str):
        raise ValueError("customer_id é obrigatório.")

    if not isinstance(items, list) or not items:
        raise ValueError("O pedido precisa conter pelo menos um produto.")

    total_amount = Decimal("0")
    processed_items = []

    for item in items:
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

    # Montagem do pedido
    order = {
        "order_id": str(uuid4()),
        "customer_id": customer_id,
        "items": processed_items,
        "total_amount": total_amount,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Persistência no DynamoDB
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("Orders")

    table.put_item(Item=order)

    # Publicação do evento no SQS
    message = {
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"],
        "customer_id": order["customer_id"],
        "total_amount": str(order["total_amount"]),
        "status": order["status"],
        "created_at": order["created_at"]
    }

    send_message(
        queue_url=SQS_QUEUE_URL,
        message_body=json.dumps(message)
    )

    return order
