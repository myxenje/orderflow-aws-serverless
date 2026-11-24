import json
import pytest
from uuid import uuid4
from boto3.dynamodb.conditions import Attr
from src.functions.cadastrador.service import create_order
from src.functions.reservador.service import reserve_order
from src.shared.database.dynamodb import get_dynamodb_resource


def test_reserve_order_success():
    # 1. Cria pedido de teste
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 2,
                "unit_price": "50.00"
            }
        ]
    })

    dynamodb = get_dynamodb_resource()

    # 2. Cria evento ORDER_CREATED
    event_id = str(uuid4())

    event = {
        "event_id": event_id,
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    # 3. Executa a reserva
    result = reserve_order(event)

    assert result["status"] == "RESERVED"

    # 4. Verifica se o pedido foi atualizado
    orders_table = dynamodb.Table("Orders")

    order_response = orders_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    saved_order = order_response["Item"]

    assert saved_order["status"] == "RESERVED"
    assert "reserved_at" in saved_order

    # 5. Verifica o registro de idempotência
    processed_table = dynamodb.Table("ProcessedEvents")

    processed_response = processed_table.get_item(
        Key={
            "consumer_event_id": f"reservador#{event_id}"
        }
    )

    assert "Item" in processed_response

    # 6. Verifica se ORDER_RESERVED foi gravado na Outbox
    outbox_table = dynamodb.Table("Outbox")

    outbox_response = outbox_table.scan(
        FilterExpression=(
            Attr("event_type").eq("ORDER_RESERVED")
            & Attr("payload").contains(order["order_id"])
        )
    )

    reserved_events = outbox_response.get("Items", [])

    assert len(reserved_events) >= 1

    reserved_event = reserved_events[-1]

    assert reserved_event["status"] == "PENDING"

    reserved_payload = json.loads(reserved_event["payload"])

    assert reserved_payload["event_type"] == "ORDER_RESERVED"
    assert reserved_payload["order_id"] == order["order_id"]
    assert reserved_payload["status"] == "RESERVED"


def test_reserve_order_duplicate_event():
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-002",
                "quantity": 1,
                "unit_price": "75.00"
            }
        ]
    })

    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    first_result = reserve_order(event)
    second_result = reserve_order(event)

    assert first_result["status"] == "RESERVED"
    assert second_result["status"] == "RESERVED"


def test_different_event_cannot_reserve_already_reserved_order():
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-003",
                "quantity": 1,
                "unit_price": "100.00"
            }
        ]
    })

    first_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    second_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    # Primeiro evento reserva o pedido
    first_result = reserve_order(first_event)

    assert first_result["status"] == "RESERVED"

    # Segundo evento deve ser rejeitado
    with pytest.raises(
        ValueError,
        match="Pedido já foi reservado por outro evento."
    ):
        reserve_order(second_event)

    # Confirma que o segundo evento não foi registrado
    dynamodb = get_dynamodb_resource()
    processed_table = dynamodb.Table("ProcessedEvents")

    response = processed_table.get_item(
        Key={
            "consumer_event_id": (
                f"reservador#{second_event['event_id']}"
            )
        }
    )

    assert "Item" not in response