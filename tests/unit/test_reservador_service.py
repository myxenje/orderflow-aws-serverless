import json
from unittest.mock import MagicMock
import pytest
from src.functions.reservador.service import reserve_order


@pytest.fixture
def dynamodb_mocks(monkeypatch):
    resource = MagicMock()
    orders_table = MagicMock()
    processed_table = MagicMock()
    outbox_table = MagicMock()
    client = MagicMock()

    tables = {
        "Orders": orders_table,
        "ProcessedEvents": processed_table,
        "Outbox": outbox_table,
    }

    resource.Table.side_effect = lambda name: tables[name]

    monkeypatch.setattr(
        "src.functions.reservador.service.get_dynamodb_resource",
        lambda: resource,
    )

    monkeypatch.setattr(
        "src.functions.reservador.service.get_dynamodb_client",
        lambda: client,
    )

    monkeypatch.setattr(
        "src.functions.reservador.service.SQS_ORDER_RESERVED_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/order-reserved",
    )

    send_message = MagicMock()

    monkeypatch.setattr(
        "src.functions.reservador.service.send_message",
        send_message,
    )

    return {
        "orders": orders_table,
        "processed": processed_table,
        "outbox": outbox_table,
        "client": client,
        "send_message": send_message,
    }


@pytest.fixture
def valid_event():
    return {
        "event_id": "event-001",
        "event_type": "ORDER_CREATED",
        "order_id": "order-001",
    }


@pytest.fixture
def pending_order():
    return {
        "order_id": "order-001",
        "customer_id": "customer-001",
        "total_amount": "100.00",
        "status": "PENDING",
    }


def test_reserve_order_success(
    dynamodb_mocks, valid_event, pending_order
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {
        "Item": pending_order
    }

    # Recupera o payload efetivamente gravado na transação.
    def get_outbox_item(**kwargs):
        transaction = mocks["client"].transact_write_items.call_args.kwargs[
            "TransactItems"
        ]

        outbox_item = transaction[2]["Put"]["Item"]

        return {
            "Item": {
                "event_id": outbox_item["event_id"]["S"],
                "payload": outbox_item["payload"]["S"],
            }
        }

    mocks["outbox"].get_item.side_effect = get_outbox_item

    result = reserve_order(valid_event)

    assert result["status"] == "RESERVED"
    assert result["message"] == "Pedido reservado com sucesso."

    mocks["client"].transact_write_items.assert_called_once()

    transaction = mocks["client"].transact_write_items.call_args.kwargs[
        "TransactItems"
    ]

    assert len(transaction) == 3
    assert transaction[0]["Update"]["TableName"] == "Orders"
    assert transaction[1]["Put"]["TableName"] == "ProcessedEvents"
    assert transaction[2]["Put"]["TableName"] == "Outbox"

    processed_item = transaction[1]["Put"]["Item"]

    assert processed_item["consumer_event_id"]["S"] == (
        "reservador#event-001"
    )
    assert "reserved_event_id" in processed_item

    outbox_item = transaction[2]["Put"]["Item"]

    assert outbox_item["event_type"]["S"] == "ORDER_RESERVED"

    payload = json.loads(outbox_item["payload"]["S"])

    assert payload["event_type"] == "ORDER_RESERVED"
    assert payload["order_id"] == "order-001"
    assert payload["customer_id"] == "customer-001"

    mocks["outbox"].get_item.assert_called_once()

    mocks["send_message"].assert_called_once_with(
        queue_url=(
            "https://sqs.us-east-1.amazonaws.com/"
            "123456789012/order-reserved"
        ),
        message_body=outbox_item["payload"]["S"],
    )


def test_reserve_order_without_event_id(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "event_id": ""}

    with pytest.raises(ValueError, match="event_id"):
        reserve_order(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_reserve_order_without_order_id(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "order_id": ""}

    with pytest.raises(ValueError, match="order_id"):
        reserve_order(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_reserve_order_duplicate_event(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {
        "Item": {
            "consumer_event_id": "reservador#event-001",
            "reserved_event_id": "reserved-event-001",
        }
    }

    mocks["outbox"].get_item.return_value = {
        "Item": {
            "event_id": "reserved-event-001",
            "event_type": "ORDER_RESERVED",
            "payload": (
                '{"event_type": "ORDER_RESERVED", '
                '"order_id": "order-001"}'
            ),
        }
    }

    result = reserve_order(valid_event)

    assert result["status"] == "RESERVED"
    assert result["message"] == "Evento já processado."

    mocks["orders"].get_item.assert_not_called()
    mocks["client"].transact_write_items.assert_not_called()

    mocks["outbox"].get_item.assert_called_once_with(
        Key={"event_id": "reserved-event-001"}
    )

    mocks["send_message"].assert_called_once()


def test_reserve_order_duplicate_event_without_reserved_event_id(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {
        "Item": {
            "consumer_event_id": "reservador#event-001",
        }
    }

    result = reserve_order(valid_event)

    assert result["status"] == "RESERVED"
    assert result["message"] == "Evento já processado."

    mocks["orders"].get_item.assert_not_called()
    mocks["outbox"].get_item.assert_not_called()
    mocks["send_message"].assert_not_called()
    mocks["client"].transact_write_items.assert_not_called()


def test_reserve_order_not_found(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {}

    with pytest.raises(ValueError, match="Pedido não encontrado"):
        reserve_order(valid_event)

    mocks["client"].transact_write_items.assert_not_called()
    mocks["send_message"].assert_not_called()


def test_reserve_order_already_reserved(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {
        "Item": {
            "order_id": "order-001",
            "status": "RESERVED",
        }
    }

    with pytest.raises(
        ValueError,
        match="reservado por outro evento",
    ):
        reserve_order(valid_event)

    mocks["client"].transact_write_items.assert_not_called()
    mocks["send_message"].assert_not_called()


def test_reserve_order_invalid_status(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {
        "Item": {
            "order_id": "order-001",
            "status": "PAID",
        }
    }

    with pytest.raises(
        ValueError,
        match="não está disponível para reserva",
    ):
        reserve_order(valid_event)

    mocks["client"].transact_write_items.assert_not_called()
    mocks["send_message"].assert_not_called()