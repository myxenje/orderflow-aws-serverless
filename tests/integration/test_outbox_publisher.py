from boto3.dynamodb.types import TypeSerializer
from src.functions.coletor.service import publish_stream_events
from src.shared.config.settings import SQS_ORDER_CREATED_QUEUE_URL


def test_outbox_stream_publishes_order_to_processing_queue(monkeypatch):
    serializer = TypeSerializer()

    payload = '{"order_id": "order-001"}'

    new_image = {
        "event_id": "event-001",
        "event_type": "ORDER_CREATED",
        "payload": payload,
        "status": "PENDING",
    }

    record = {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                key: serializer.serialize(value)
                for key, value in new_image.items()
            }
        },
    }

    published_messages = []

    def mock_send_message(queue_url, message_body):
        published_messages.append({
            "queue_url": queue_url,
            "message_body": message_body,
        })

    monkeypatch.setattr(
        "src.functions.coletor.service.send_message",
        mock_send_message,
    )

    publish_stream_events(record)

    assert published_messages == [{
        "queue_url": SQS_ORDER_CREATED_QUEUE_URL,
        "message_body": payload,
    }]