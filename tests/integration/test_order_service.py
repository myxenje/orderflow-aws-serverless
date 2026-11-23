from src.functions.cadastrador.service import create_order
from src.shared.database.dynamodb import get_dynamodb_resource


def test_create_order():
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
