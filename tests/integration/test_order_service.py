import json
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

    dynamodb = get_dynamodb_resource()

    # Verifica se o pedido foi salvo
    orders_table = dynamodb.Table("Orders")
    order_response = orders_table.get_item(
        Key={"order_id": order["order_id"]}
    )

    assert "Item" in order_response
    assert order_response["Item"]["customer_id"] == "customer-001"

    # Verifica se o evento foi salvo na Outbox
    outbox_table = dynamodb.Table("Outbox")
    outbox_response = outbox_table.scan(
        FilterExpression="#status = :status",
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":status": "PENDING"
        }
    )

    matching_events = [
        event for event in outbox_response["Items"]
        if json.loads(event["payload"])["order_id"] == order["order_id"]
    ]

    assert len(matching_events) == 1

    event = matching_events[0]

    assert event["event_type"] == "ORDER_CREATED"
    assert event["status"] == "PENDING"

    message = json.loads(event["payload"])

    assert message["event_type"] == "ORDER_CREATED"
    assert message["order_id"] == order["order_id"]
    assert message["customer_id"] == "customer-001"
    assert message["total_amount"] == "130.00"