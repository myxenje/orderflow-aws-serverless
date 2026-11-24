import json
import pytest
from uuid import uuid4
from boto3.dynamodb.conditions import Attr
from src.functions.cadastrador.service import create_order
from src.functions.reservador.service import reserve_order
from src.functions.pagador.service import process_payment
from src.functions.estornador.service import process_refund
from src.shared.database.dynamodb import get_dynamodb_resource


def create_paid_order():
    # 1. Cria um pedido
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-refund-001",
                "quantity": 2,
                "unit_price": "50.00"
            }
        ]
    })

    # 2. Reserva o pedido
    reservation_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    reserve_order(reservation_event)

    # 3. Processa o pagamento
    payment_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    payment_result = process_payment(payment_event)

    return order, payment_result["payment_id"]

def test_process_refund_success():
    order, payment_id = create_paid_order()

    # 1. Cria evento de solicitação de estorno
    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order["order_id"],
        "payment_id": payment_id
    }

    # 2. Processa o estorno
    result = process_refund(event)

    assert result["status"] == "REFUNDED"
    assert result["payment_id"] == payment_id

    # 3. Verifica atualização do pedido
    dynamodb = get_dynamodb_resource()

    orders_table = dynamodb.Table("Orders")

    response = orders_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    saved_order = response["Item"]

    assert saved_order["status"] == "REFUNDED"
    assert saved_order["payment_id"] == payment_id
    assert "refunded_at" in saved_order

    # 4. Verifica registro de idempotência
    processed_table = dynamodb.Table("ProcessedEvents")

    processed_response = processed_table.get_item(
        Key={
            "consumer_event_id": f"estornador#{event['event_id']}"
        }
    )

    assert "Item" in processed_response
    assert processed_response["Item"]["payment_id"] == payment_id

    # 5. Verifica evento ORDER_REFUNDED na Outbox
    outbox_table = dynamodb.Table("Outbox")

    outbox_response = outbox_table.scan(
        FilterExpression=(
            Attr("event_type").eq("ORDER_REFUNDED")
            & Attr("payload").contains(order["order_id"])
        )
    )

    refunded_events = outbox_response.get("Items", [])

    assert len(refunded_events) >= 1

    refunded_event = refunded_events[-1]

    assert refunded_event["status"] == "PENDING"

    refunded_payload = json.loads(refunded_event["payload"])

    assert refunded_payload["event_type"] == "ORDER_REFUNDED"
    assert refunded_payload["order_id"] == order["order_id"]
    assert refunded_payload["payment_id"] == payment_id
    assert refunded_payload["status"] == "REFUNDED"


def test_process_refund_duplicate_event():
    order, payment_id = create_paid_order()

    event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order["order_id"],
        "payment_id": payment_id
    }

    # Primeira execução
    first_result = process_refund(event)

    # Segunda execução com o mesmo evento
    second_result = process_refund(event)

    assert first_result["status"] == "REFUNDED"
    assert second_result["status"] == "REFUNDED"

    assert first_result["payment_id"] == second_result["payment_id"]
    assert first_result["payment_id"] == payment_id

def test_different_event_cannot_refund_already_refunded_order():
    order, payment_id = create_paid_order()

    first_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order["order_id"],
        "payment_id": payment_id
    }

    second_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order["order_id"],
        "payment_id": payment_id
    }

    # Primeiro evento realiza o estorno
    first_result = process_refund(first_event)

    assert first_result["status"] == "REFUNDED"

    # Segundo evento deve ser rejeitado
    with pytest.raises(
        ValueError,
        match="Pedido já foi estornado por outro evento."
    ):
        process_refund(second_event)

    # Confirma que o segundo evento não foi registrado
    dynamodb = get_dynamodb_resource()

    processed_table = dynamodb.Table("ProcessedEvents")

    response = processed_table.get_item(
        Key={
            "consumer_event_id": (
                f"estornador#{second_event['event_id']}"
            )
        }
    )

    assert "Item" not in response
