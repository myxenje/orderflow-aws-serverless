import json
import pytest
from uuid import uuid4
from boto3.dynamodb.conditions import Attr
from src.functions.cadastrador.service import create_order
from src.functions.reservador.service import reserve_order
from src.functions.pagador.service import process_payment
from src.shared.database.dynamodb import get_dynamodb_resource


def create_stock_product(product_id, quantity=10):
    dynamodb = get_dynamodb_resource()
    stock_table = dynamodb.Table("Stock")

    stock_table.put_item(
        Item={
            "product_id": product_id,
            "quantity": quantity,
        }
    )


def create_reserved_order():
    product_id = "product-payment-001"

    # Garante que o produto exista e tenha estoque disponível.
    create_stock_product(product_id, quantity=10)

    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": product_id,
                "quantity": 2,
                "unit_price": "50.00"
            }
        ]
    })

    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    reserve_order(event)

    return order


def test_process_payment_success():
    order = create_reserved_order()

    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    result = process_payment(event)

    assert result["status"] == "PAID"
    assert "payment_id" in result

    dynamodb = get_dynamodb_resource()

    orders_table = dynamodb.Table("Orders")

    response = orders_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    saved_order = response["Item"]

    assert saved_order["status"] == "PAID"
    assert saved_order["payment_id"] == result["payment_id"]
    assert "paid_at" in saved_order

    processed_table = dynamodb.Table("ProcessedEvents")

    processed_response = processed_table.get_item(
        Key={
            "consumer_event_id": f"pagador#{event['event_id']}"
        }
    )

    assert "Item" in processed_response

    # Verifica evento ORDER_PAID na Outbox.
    outbox_table = dynamodb.Table("Outbox")

    outbox_response = outbox_table.scan(
        FilterExpression=(
            Attr("event_type").eq("ORDER_PAID")
            & Attr("payload").contains(order["order_id"])
        )
    )

    paid_events = outbox_response.get("Items", [])

    assert len(paid_events) >= 1

    paid_event = paid_events[-1]

    assert paid_event["status"] == "PENDING"

    paid_payload = json.loads(paid_event["payload"])

    assert paid_payload["event_type"] == "ORDER_PAID"
    assert paid_payload["order_id"] == order["order_id"]
    assert paid_payload["status"] == "PAID"


def test_process_payment_duplicate_event():
    order = create_reserved_order()

    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    first_result = process_payment(event)
    second_result = process_payment(event)

    assert first_result["status"] == "PAID"
    assert second_result["status"] == "PAID"

    assert first_result["payment_id"] == second_result["payment_id"]


def test_different_event_cannot_pay_already_paid_order():
    order = create_reserved_order()

    first_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    second_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    # Primeiro evento processa o pagamento.
    first_result = process_payment(first_event)

    assert first_result["status"] == "PAID"

    # Segundo evento deve ser rejeitado.
    with pytest.raises(
        ValueError,
        match="Pedido já foi pago por outro evento."
    ):
        process_payment(second_event)

    # Confirma que o segundo evento não foi registrado.
    dynamodb = get_dynamodb_resource()

    processed_table = dynamodb.Table("ProcessedEvents")

    response = processed_table.get_item(
        Key={
            "consumer_event_id": (
                f"pagador#{second_event['event_id']}"
            )
        }
    )

    assert "Item" not in response