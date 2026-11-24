from unittest.mock import MagicMock
import pytest
from src.functions.faturador.service import generate_invoice


@pytest.fixture
def dynamodb_mocks(monkeypatch):
    resource = MagicMock()
    invoices_table = MagicMock()
    processed_table = MagicMock()
    client = MagicMock()

    resource.Table.side_effect = lambda name: {
        "Invoices": invoices_table,
        "ProcessedEvents": processed_table,
    }[name]

    monkeypatch.setattr(
        "src.functions.faturador.service.get_dynamodb_resource",
        lambda: resource
    )

    monkeypatch.setattr(
        "src.functions.faturador.service.get_dynamodb_client",
        lambda: client
    )

    return {
        "invoices": invoices_table,
        "processed": processed_table,
        "client": client,
    }


@pytest.fixture
def valid_event():
    return {
        "event_id": "event-001",
        "event_type": "ORDER_PAID",
        "order_id": "order-001",
        "customer_id": "customer-001",
        "total_amount": "100.00",
        "payment_id": "payment-001",
    }


def test_generate_invoice_success(dynamodb_mocks, valid_event):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["invoices"].get_item.return_value = {}

    result = generate_invoice(valid_event)

    assert result["status"] == "INVOICED"
    assert result["message"] == "Fatura gerada com sucesso."
    assert result["invoice_id"]

    mocks["client"].transact_write_items.assert_called_once()

    transaction = mocks["client"].transact_write_items.call_args.kwargs[
        "TransactItems"
    ]

    assert len(transaction) == 3
    assert transaction[0]["Put"]["TableName"] == "Invoices"
    assert transaction[1]["Put"]["TableName"] == "ProcessedEvents"
    assert transaction[2]["Put"]["TableName"] == "Outbox"


def test_generate_invoice_without_event_id(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "event_id": ""}

    with pytest.raises(ValueError, match="event_id"):
        generate_invoice(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_generate_invoice_without_order_id(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "order_id": ""}

    with pytest.raises(ValueError, match="order_id"):
        generate_invoice(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_generate_invoice_invalid_event_type(
    dynamodb_mocks, valid_event
):
    event = {**valid_event, "event_type": "ORDER_CREATED"}

    with pytest.raises(ValueError, match="Tipo de evento"):
        generate_invoice(event)

    dynamodb_mocks["client"].transact_write_items.assert_not_called()


def test_generate_invoice_duplicate_event(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {
        "Item": {
            "consumer_event_id": "faturador#event-001",
            "invoice_id": "invoice-001"
        }
    }

    result = generate_invoice(valid_event)

    assert result["status"] == "INVOICED"
    assert result["invoice_id"] == "invoice-001"
    assert result["message"] == "Evento já processado."

    mocks["invoices"].get_item.assert_not_called()
    mocks["client"].transact_write_items.assert_not_called()


def test_generate_invoice_order_already_has_invoice(
    dynamodb_mocks, valid_event
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["invoices"].get_item.return_value = {
        "Item": {
            "order_id": "order-001",
            "invoice_id": "invoice-existing"
        }
    }

    with pytest.raises(ValueError, match="já possui uma fatura"):
        generate_invoice(valid_event)

    mocks["client"].transact_write_items.assert_not_called()


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("customer_id", "customer_id"),
        ("total_amount", "total_amount"),
        ("payment_id", "payment_id"),
    ]
)
def test_generate_invoice_missing_required_data(
    dynamodb_mocks, valid_event, field, message
):
    mocks = dynamodb_mocks

    mocks["processed"].get_item.return_value = {}
    mocks["invoices"].get_item.return_value = {}

    event = {**valid_event, field: None}

    with pytest.raises(ValueError, match=message):
        generate_invoice(event)

    mocks["client"].transact_write_items.assert_not_called()