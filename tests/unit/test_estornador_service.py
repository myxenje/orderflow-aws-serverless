from unittest.mock import MagicMock
from botocore.exceptions import ClientError
import pytest
from src.functions.estornador.service import process_refund


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
        "src.functions.estornador.service.get_dynamodb_resource",
        lambda: resource
    )

    monkeypatch.setattr(
        "src.functions.estornador.service.get_dynamodb_client",
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
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": "order-001",
        "payment_id": "payment-001",
    }


@pytest.fixture
def paid_order():
    return {
        "order_id": "order-001",
        "customer_id": "customer-001",
        "total_amount": "100.00",
        "payment_id": "payment-001",
        "status": "PAID",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 2,
                "unit_price": "50.00",
            }
        ],
    }

def test_process_refund_success(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {"Item": paid_order}

    result = process_refund(valid_event)

    assert result["status"] == "REFUNDED"
    assert result["payment_id"] == "payment-001"
    assert result["message"] == "Estorno processado com sucesso."

    mocks["client"].transact_write_items.assert_called_once()

    transaction = mocks["client"].transact_write_items.call_args.kwargs[
        "TransactItems"
    ]

    assert len(transaction) == 4
    assert transaction[0]["Update"]["TableName"] == "Orders"
    assert transaction[1]["Update"]["TableName"] == "Stock"
    assert transaction[2]["Put"]["TableName"] == "ProcessedEvents"
    assert transaction[3]["Put"]["TableName"] == "Outbox"

    assert (
        transaction[0]["Update"]["ExpressionAttributeValues"][":status"]["S"]
        == "REFUNDED"
    )

    assert (
        transaction[3]["Put"]["Item"]["event_type"]["S"]
        == "ORDER_REFUNDED"
    )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("event_id", "event_id"),
        ("order_id", "order_id"),
        ("payment_id", "payment_id"),
    ]
)
def test_process_refund_missing_required_fields(
    dynamodb_mocks, valid_event, field, message
):
    event = {**valid_event, field: ""}

    with pytest.raises(ValueError, match=message):
        process_refund(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_invalid_event_type(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "event_type": "ORDER_PAID"}

    with pytest.raises(ValueError, match="ORDER_REFUND_REQUESTED"):
        process_refund(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_duplicate_event(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {
        "Item": {
            "consumer_event_id": "estornador#event-001",
            "payment_id": "payment-001",
        }
    }

    result = process_refund(valid_event)

    assert result["status"] == "REFUNDED"
    assert result["payment_id"] == "payment-001"
    assert result["message"] == "Evento já processado."

    mocks["orders"].get_item.assert_not_called()
    mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_order_not_found(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {}

    with pytest.raises(ValueError, match="Pedido não encontrado"):
        process_refund(valid_event)

    mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_order_already_refunded(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    refunded_order = {**paid_order, "status": "REFUNDED"}

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {"Item": refunded_order}

    with pytest.raises(ValueError, match="já foi estornado"):
        process_refund(valid_event)

    mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_order_not_paid(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    reserved_order = {**paid_order, "status": "RESERVED"}

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {"Item": reserved_order}

    with pytest.raises(ValueError, match="não está disponível"):
        process_refund(valid_event)

    mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_invalid_payment_id(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {"Item": paid_order}

    event = {**valid_event, "payment_id": "payment-wrong"}

    with pytest.raises(ValueError, match="não corresponde"):
        process_refund(event)

    mocks["client"].transact_write_items.assert_not_called()


def test_process_refund_concurrent_duplicate_event(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.side_effect = [
        {},
        {
            "Item": {
                "consumer_event_id": "estornador#event-001",
                "payment_id": "payment-001",
            }
        }
    ]

    mocks["orders"].get_item.return_value = {"Item": paid_order}

    mocks["client"].transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            }
        },
        "TransactWriteItems"
    )

    result = process_refund(valid_event)

    assert result["status"] == "REFUNDED"
    assert result["payment_id"] == "payment-001"
    assert result["message"] == "Evento já processado."


def test_process_refund_order_refunded_by_another_event(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    refunded_order = {**paid_order, "status": "REFUNDED"}

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.side_effect = [
        {"Item": paid_order},
        {"Item": refunded_order},
    ]

    mocks["client"].transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            }
        },
        "TransactWriteItems"
    )

    with pytest.raises(ValueError, match="já foi estornado"):
        process_refund(valid_event)


def test_process_refund_unexpected_dynamodb_error(
    dynamodb_mocks, valid_event, paid_order
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["orders"].get_item.return_value = {"Item": paid_order}

    mocks["client"].transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "InternalServerError",
                "Message": "Unexpected error",
            }
        },
        "TransactWriteItems"
    )

    with pytest.raises(ClientError):
        process_refund(valid_event)