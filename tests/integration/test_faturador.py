import json
import pytest
from uuid import uuid4
from boto3.dynamodb.conditions import Attr
from src.functions.cadastrador.service import create_order
from src.functions.reservador.service import reserve_order
from src.functions.pagador.service import process_payment
from src.functions.faturador.service import generate_invoice
from src.shared.database.dynamodb import get_dynamodb_resource


def create_paid_order():
    # 1. Cria um pedido
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-invoice-001",
                "quantity": 2,
                "unit_price": "50.00"
            }
        ]
    })

    # 2. Reserva o pedido
    reserve_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_CREATED",
        "order_id": order["order_id"]
    }

    reserve_order(reserve_event)

    # 3. Processa o pagamento
    payment_event = {
        "event_id": str(uuid4()),
        "event_type": "ORDER_RESERVED",
        "order_id": order["order_id"]
    }

    process_payment(payment_event)

    # 4. Recupera o evento ORDER_PAID gerado pelo Pagador
    dynamodb = get_dynamodb_resource()
    outbox_table = dynamodb.Table("Outbox")

    response = outbox_table.scan(
        FilterExpression=(
            Attr("event_type").eq("ORDER_PAID")
            & Attr("payload").contains(order["order_id"])
        )
    )

    paid_events = response.get("Items", [])

    assert paid_events, "Evento ORDER_PAID não encontrado."

    paid_event = json.loads(paid_events[-1]["payload"])

    return order, paid_event


def test_generate_invoice_success():
    order, event = create_paid_order()

    # 1. Gera a fatura
    result = generate_invoice(event)

    assert result["status"] == "INVOICED"
    assert "invoice_id" in result

    dynamodb = get_dynamodb_resource()

    # 2. Verifica a fatura
    invoices_table = dynamodb.Table("Invoices")

    response = invoices_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    invoice = response["Item"]

    assert invoice["invoice_id"] == result["invoice_id"]
    assert invoice["customer_id"] == order["customer_id"]
    assert invoice["payment_id"] == event["payment_id"]
    assert invoice["total_amount"] == "100"
    assert invoice["status"] == "ISSUED"
    assert "created_at" in invoice

    # 3. Verifica o registro de idempotência
    processed_table = dynamodb.Table("ProcessedEvents")

    processed_response = processed_table.get_item(
        Key={
            "consumer_event_id": (
                f"faturador#{event['event_id']}"
            )
        }
    )

    assert "Item" in processed_response
    assert (
        processed_response["Item"]["invoice_id"]
        == result["invoice_id"]
    )

    # 4. Verifica o evento ORDER_INVOICED na Outbox
    outbox_table = dynamodb.Table("Outbox")

    outbox_response = outbox_table.scan(
        FilterExpression=(
            Attr("event_type").eq("ORDER_INVOICED")
            & Attr("payload").contains(order["order_id"])
        )
    )

    invoiced_events = outbox_response.get("Items", [])

    assert len(invoiced_events) >= 1

    invoiced_event = invoiced_events[-1]

    assert invoiced_event["status"] == "PENDING"

    invoiced_payload = json.loads(invoiced_event["payload"])

    assert invoiced_payload["event_type"] == "ORDER_INVOICED"
    assert invoiced_payload["order_id"] == order["order_id"]
    assert invoiced_payload["invoice_id"] == result["invoice_id"]
    assert invoiced_payload["status"] == "INVOICED"


def test_generate_invoice_duplicate_event():
    order, event = create_paid_order()

    first_result = generate_invoice(event)
    second_result = generate_invoice(event)

    assert first_result["status"] == "INVOICED"
    assert second_result["status"] == "INVOICED"

    assert (
        first_result["invoice_id"]
        == second_result["invoice_id"]
    )

    dynamodb = get_dynamodb_resource()

    invoices_table = dynamodb.Table("Invoices")

    response = invoices_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    assert response["Item"]["invoice_id"] == first_result["invoice_id"]


def test_different_event_cannot_generate_second_invoice():
    order, first_event = create_paid_order()

    # Primeiro evento gera a fatura
    first_result = generate_invoice(first_event)

    assert first_result["status"] == "INVOICED"

    # Segundo evento tenta faturar o mesmo pedido
    second_event = {
        **first_event,
        "event_id": str(uuid4())
    }

    with pytest.raises(
        ValueError,
        match="Pedido já possui uma fatura."
    ):
        generate_invoice(second_event)

    # Confirma que o segundo evento não foi processado
    dynamodb = get_dynamodb_resource()

    processed_table = dynamodb.Table("ProcessedEvents")

    response = processed_table.get_item(
        Key={
            "consumer_event_id": (
                f"faturador#{second_event['event_id']}"
            )
        }
    )

    assert "Item" not in response

    # Confirma que existe somente uma fatura para o pedido
    invoices_table = dynamodb.Table("Invoices")

    invoice_response = invoices_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    assert invoice_response["Item"]["invoice_id"] == first_result["invoice_id"]