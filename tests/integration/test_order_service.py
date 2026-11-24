import json
from unittest.mock import patch

from src.functions.cadastrador.service import create_order
from src.shared.database.dynamodb import get_dynamodb_resource
from src.shared.config.settings import SQS_QUEUE_URL


@patch("src.functions.cadastrador.service.send_message")
def test_create_order(mock_send_message):
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

    # Valida os dados do pedido
    assert order["order_id"]
    assert order["customer_id"] == "customer-001"
    assert order["status"] == "PENDING"
    assert order["total_amount"] == 130

    # Confirma que o pedido foi salvo no DynamoDB
    table = get_dynamodb_resource().Table("Orders")
    response = table.get_item(
        Key={"order_id": order["order_id"]}
    )

    assert "Item" in response
    assert response["Item"]["customer_id"] == "customer-001"

    # Confirma que o evento foi enviado ao SQS
    mock_send_message.assert_called_once()

    call_args = mock_send_message.call_args.kwargs

    assert call_args["queue_url"] == SQS_QUEUE_URL

    message = json.loads(call_args["message_body"])

    assert message["event_type"] == "ORDER_CREATED"
    assert message["order_id"] == order["order_id"]
    assert message["customer_id"] == "customer-001"
    assert message["total_amount"] == "130.00"
    assert message["status"] == "PENDING"