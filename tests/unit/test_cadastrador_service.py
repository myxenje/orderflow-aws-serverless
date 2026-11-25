from decimal import Decimal
from unittest.mock import patch
import pytest
from botocore.exceptions import ClientError
from src.functions.cadastrador.service import create_order, request_refund


@patch("src.functions.cadastrador.service.transact_write_items")
def test_create_order_success(mock_transact):
    order_data = {
        "customer_id": "customer-001",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 2,
                "unit_price": "50.00"
            },
            {
                "product_id": "product-002",
                "quantity": 1,
                "unit_price": "30.00"
            }
        ]
    }

    order = create_order(order_data)

    assert order["customer_id"] == "customer-001"
    assert order["status"] == "PENDING"
    assert order["total_amount"] == Decimal("130.00")
    assert len(order["items"]) == 2

    assert order["items"][0]["subtotal"] == Decimal("100.00")
    assert order["items"][1]["subtotal"] == Decimal("30.00")

    mock_transact.assert_called_once()


@patch("src.functions.cadastrador.service.transact_write_items")
def test_create_order_without_customer_id(mock_transact):
    order_data = {
        "customer_id": "",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 1,
                "unit_price": "50.00"
            }
        ]
    }

    with pytest.raises(ValueError, match="customer_id"):
        create_order(order_data)

    mock_transact.assert_not_called()


@patch("src.functions.cadastrador.service.transact_write_items")
def test_create_order_without_items(mock_transact):
    order_data = {
        "customer_id": "customer-001",
        "items": []
    }

    with pytest.raises(ValueError, match="pelo menos um produto"):
        create_order(order_data)

    mock_transact.assert_not_called()


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2"])
@patch("src.functions.cadastrador.service.transact_write_items")
def test_create_order_with_invalid_quantity(mock_transact, quantity):
    order_data = {
        "customer_id": "customer-001",
        "items": [
            {
                "product_id": "product-001",
                "quantity": quantity,
                "unit_price": "50.00"
            }
        ]
    }

    with pytest.raises(ValueError, match="quantity"):
        create_order(order_data)

    mock_transact.assert_not_called()


@pytest.mark.parametrize("unit_price", ["abc", "0", "-10", "NaN", "Infinity"])
@patch("src.functions.cadastrador.service.transact_write_items")
def test_create_order_with_invalid_unit_price(mock_transact, unit_price):
    order_data = {
        "customer_id": "customer-001",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 1,
                "unit_price": unit_price
            }
        ]
    }

    with pytest.raises(ValueError, match="unit_price"):
        create_order(order_data)

    mock_transact.assert_not_called()

@patch("src.functions.cadastrador.service.transact_write_items")
@patch("src.functions.cadastrador.service.get_dynamodb_resource")
def test_request_refund_success(mock_dynamodb, mock_transact):
    order = {
        "order_id": "order-001",
        "customer_id": "customer-001",
        "status": "PAID",
        "payment_id": "payment-001",
        "total_amount": Decimal("100.00")
    }

    mock_table = mock_dynamodb.return_value.Table.return_value
    mock_table.get_item.return_value = {"Item": order}

    result = request_refund("order-001")

    assert result["event_type"] == "ORDER_REFUND_REQUESTED"
    assert result["order_id"] == "order-001"
    assert result["payment_id"] == "payment-001"

    mock_transact.assert_called_once()

@patch("src.functions.cadastrador.service.transact_write_items")
@patch("src.functions.cadastrador.service.get_dynamodb_resource")
def test_request_refund_order_not_found(mock_dynamodb, mock_transact):
    mock_table = mock_dynamodb.return_value.Table.return_value
    mock_table.get_item.return_value = {}

    with pytest.raises(ValueError, match="Pedido não encontrado"):
        request_refund("order-001")

    mock_transact.assert_not_called()

@patch("src.functions.cadastrador.service.transact_write_items")
@patch("src.functions.cadastrador.service.get_dynamodb_resource")
def test_request_refund_order_not_paid(mock_dynamodb, mock_transact):
    order = {
        "order_id": "order-001",
        "status": "PENDING"
    }

    mock_table = mock_dynamodb.return_value.Table.return_value
    mock_table.get_item.return_value = {"Item": order}

    with pytest.raises(ValueError, match="Somente pedidos pagos"):
        request_refund("order-001")

    mock_transact.assert_not_called()


@patch("src.functions.cadastrador.service.transact_write_items")
@patch("src.functions.cadastrador.service.get_dynamodb_resource")
def test_request_refund_duplicate(mock_dynamodb, mock_transact):
    order = {
        "order_id": "order-001",
        "customer_id": "customer-001",
        "status": "PAID",
        "payment_id": "payment-001",
        "total_amount": Decimal("100.00")
    }

    mock_table = mock_dynamodb.return_value.Table.return_value
    mock_table.get_item.return_value = {"Item": order}

    mock_transact.side_effect = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled"
            }
        },
        "TransactWriteItems"
    )

    with pytest.raises(ValueError, match="Já existe uma solicitação"):
        request_refund("order-001")

    mock_transact.assert_called_once()
