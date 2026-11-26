from uuid import uuid4
import pytest
from src.functions.notificador.service import notify_customer
from src.shared.database.dynamodb import get_dynamodb_resource


@pytest.fixture(autouse=True)
def mock_sns(monkeypatch):
    monkeypatch.setattr(
        "src.functions.notificador.service.publish_notification",
        lambda subject, message: {"MessageId": "test-message-id"},
    )


def create_event():
    event_id = str(uuid4())

    return {
        "event_id": event_id,
        "event_type": "ORDER_INVOICED",
        "order_id": str(uuid4()),
        "customer_id": "customer-test",
        "invoice_id": str(uuid4()),
    }


def test_notify_customer_success():
    event = create_event()

    result = notify_customer(event)

    assert result["status"] == "SENT"
    assert result["order_id"] == event["order_id"]
    assert result["customer_id"] == event["customer_id"]
    assert result["invoice_id"] == event["invoice_id"]

    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("ProcessedEvents")

    response = table.get_item(
        Key={
            "consumer_event_id": f"notificador#{event['event_id']}"
        }
    )

    item = response.get("Item")

    assert item is not None
    assert item["consumer_name"] == "notificador"
    assert item["status"] == "SENT"


def test_notify_customer_duplicate_event():
    event = create_event()

    first_result = notify_customer(event)
    second_result = notify_customer(event)

    assert first_result["status"] == "SENT"
    assert second_result["status"] == "DUPLICATE"
    assert second_result["order_id"] == event["order_id"]


def test_notify_customer_invalid_event_type():
    event = create_event()
    event["event_type"] = "ORDER_PAID"

    with pytest.raises(ValueError, match="ORDER_INVOICED"):
        notify_customer(event)