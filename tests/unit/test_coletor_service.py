import pytest
from boto3.dynamodb.types import TypeSerializer
from src.functions.coletor import service


@pytest.fixture
def stream_record():
    serializer = TypeSerializer()

    new_image = {
        "event_id": "event-001",
        "event_type": "ORDER_CREATED",
        "payload": '{"order_id": "order-001"}',
        "status": "PENDING",
    }

    return {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                key: serializer.serialize(value)
                for key, value in new_image.items()
            }
        },
    }


def test_publish_stream_events_success(monkeypatch, stream_record):
    send_mock = pytest.MonkeyPatch()
    calls = []

    def mock_send_message(queue_url, message_body):
        calls.append({
            "queue_url": queue_url,
            "message_body": message_body,
        })

    monkeypatch.setattr(service, "send_message", mock_send_message)
    monkeypatch.setattr(
        service,
        "SQS_ORDER_CREATED_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/000000000000/order-processing",
    )

    service.publish_stream_events(stream_record)

    assert calls == [{
        "queue_url": service.SQS_ORDER_CREATED_QUEUE_URL,
        "message_body": '{"order_id": "order-001"}',
    }]


def test_publish_stream_events_ignores_non_insert(monkeypatch):
    calls = []

    monkeypatch.setattr(
        service,
        "send_message",
        lambda **kwargs: calls.append(kwargs),
    )

    service.publish_stream_events({
        "eventName": "MODIFY",
        "dynamodb": {},
    })

    assert calls == []


def test_publish_stream_events_missing_new_image():
    with pytest.raises(ValueError, match="NewImage"):
        service.publish_stream_events({
            "eventName": "INSERT",
            "dynamodb": {},
        })


def test_publish_stream_events_missing_payload(stream_record):
    stream_record["dynamodb"]["NewImage"].pop("payload")

    with pytest.raises(ValueError, match="Payload"):
        service.publish_stream_events(stream_record)


def test_publish_stream_events_send_failure(monkeypatch, stream_record):
    def mock_send_message(**kwargs):
        raise Exception("SQS unavailable")

    monkeypatch.setattr(service, "send_message", mock_send_message)

    with pytest.raises(Exception, match="SQS unavailable"):
        service.publish_stream_events(stream_record)