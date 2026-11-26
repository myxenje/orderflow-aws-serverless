from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError
from src.functions.notificador.service import notify_customer


@pytest.fixture
def dynamodb_mocks(monkeypatch):
    resource = MagicMock()
    processed_table = MagicMock()
    sns_mock = MagicMock()

    resource.Table.return_value = processed_table

    monkeypatch.setattr(
        "src.functions.notificador.service.get_dynamodb_resource",
        lambda: resource,
    )

    monkeypatch.setattr(
        "src.functions.notificador.service.publish_notification",
        sns_mock,
    )

    return {
        "processed": processed_table,
        "sns": sns_mock,
    }


@pytest.fixture
def valid_event():
    return {
        "event_id": "event-001",
        "event_type": "ORDER_INVOICED",
        "order_id": "order-001",
        "customer_id": "customer-001",
        "invoice_id": "invoice-001",
    }


def test_notify_customer_success(dynamodb_mocks, valid_event):
    mocks = dynamodb_mocks
    mocks["processed"].get_item.return_value = {}

    result = notify_customer(valid_event)

    assert result["status"] == "SENT"
    assert result["order_id"] == "order-001"
    assert result["customer_id"] == "customer-001"
    assert result["invoice_id"] == "invoice-001"

    mocks["processed"].put_item.assert_called_once()

    notification = mocks["processed"].put_item.call_args.kwargs["Item"]

    assert notification["consumer_event_id"] == "notificador#event-001"
    assert notification["consumer_name"] == "notificador"
    assert notification["status"] == "SENT"
    assert notification["event_id"] == "event-001"
    assert notification["sent_at"]

    mocks["sns"].assert_called_once()

    sns_call = mocks["sns"].call_args.kwargs

    assert sns_call["subject"] == "Pedido order-001 faturado com sucesso"
    assert "Pedido: order-001" in sns_call["message"]
    assert "Cliente: customer-001" in sns_call["message"]
    assert "Nota fiscal: invoice-001" in sns_call["message"]


def test_notify_customer_without_event_id(dynamodb_mocks, valid_event):
    event = {**valid_event, "event_id": ""}

    with pytest.raises(ValueError, match="event_id"):
        notify_customer(event)

    dynamodb_mocks["processed"].put_item.assert_not_called()
    dynamodb_mocks["sns"].assert_not_called()


def test_notify_customer_without_order_id(dynamodb_mocks, valid_event):
    event = {**valid_event, "order_id": ""}

    with pytest.raises(ValueError, match="order_id"):
        notify_customer(event)

    dynamodb_mocks["processed"].put_item.assert_not_called()
    dynamodb_mocks["sns"].assert_not_called()


def test_notify_customer_invalid_event_type(dynamodb_mocks, valid_event):
    event = {**valid_event, "event_type": "ORDER_PAID"}

    with pytest.raises(ValueError, match="ORDER_INVOICED"):
        notify_customer(event)

    dynamodb_mocks["processed"].put_item.assert_not_called()
    dynamodb_mocks["sns"].assert_not_called()


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("customer_id", "customer_id"),
        ("invoice_id", "invoice_id"),
    ],
)
def test_notify_customer_missing_required_data(
    dynamodb_mocks, valid_event, field, message
):
    event = {**valid_event, field: ""}

    with pytest.raises(ValueError, match=message):
        notify_customer(event)

    dynamodb_mocks["processed"].put_item.assert_not_called()
    dynamodb_mocks["sns"].assert_not_called()


def test_notify_customer_duplicate_event(dynamodb_mocks, valid_event):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {
        "Item": {
            "consumer_event_id": "notificador#event-001",
            "status": "SENT",
        }
    }

    result = notify_customer(valid_event)

    assert result["status"] == "DUPLICATE"
    assert result["order_id"] == "order-001"

    mocks["processed"].put_item.assert_not_called()
    mocks["sns"].assert_not_called()


def test_notify_customer_concurrent_duplicate_event(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks
    mocks["processed"].get_item.return_value = {}

    mocks["processed"].put_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        },
        "PutItem",
    )

    result = notify_customer(valid_event)

    assert result["status"] == "DUPLICATE"
    assert result["order_id"] == "order-001"

    mocks["processed"].put_item.assert_called_once()
    mocks["sns"].assert_not_called()