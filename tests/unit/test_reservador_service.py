from unittest.mock import MagicMock
import pytest
from src.functions.reservador.service import reserve_order


@pytest.fixture
def dynamodb_mocks(monkeypatch):
    resource = MagicMock()
    orders_table = MagicMock()
    processed_table = MagicMock()
    client = MagicMock()

    resource.Table.side_effect = lambda name: {
        "Orders": orders_table,
        "ProcessedEvents": processed_table,
    }[name]

    monkeypatch.setattr(
        "src.functions.reservador.service.get_dynamodb_resource",
        lambda: resource
    )

    monkeypatch.setattr(
        "src.functions.reservador.service.get_dynamodb_client",
        lambda: client
    )

    return {
        "orders": orders_table,
        "processed": processed_table,
        "client": client,
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
            "consumer_event_id": "reservador#event-001"
        }
    }

    result = reserve_order(valid_event)

    assert result["status"] == "RESERVED"
    assert result["message"] == "Evento já processado."

    mocks["orders"].get_item.assert_not_called()
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


def test_reserve_order_already_reserved(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {
        "Item": {
            "order_id": "order-001",
            "status": "RESERVED"
        }
    }

    with pytest.raises(
        ValueError,
        match="reservado por outro evento"
    ):
        reserve_order(valid_event)

    mocks["client"].transact_write_items.assert_not_called()


def test_reserve_order_invalid_status(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {
        "Item": {
            "order_id": "order-001",
            "status": "PAID"
        }
    }

    with pytest.raises(
        ValueError,
        match="não está disponível para reserva"
    ):
        reserve_order(valid_event)

    mocks["client"].transact_write_items.assert_not_called()