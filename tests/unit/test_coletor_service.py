from unittest.mock import MagicMock, call
import pytest
from src.functions.coletor import service


@pytest.fixture
def dynamodb_mocks(monkeypatch):
    resource = MagicMock()
    table = MagicMock()

    resource.Table.return_value = table

    monkeypatch.setattr(
        service,
        "get_dynamodb_resource",
        lambda: resource
    )

    monkeypatch.setattr(
        service,
        "SQS_ORDER_CREATED_QUEUE_URL",
        "http://localhost:9324/000000000000/order-processing"
    )

    monkeypatch.setattr(
        service,
        "SQS_ORDER_RESERVED_QUEUE_URL",
        "http://localhost:9324/000000000000/order-reserved"
    )

    monkeypatch.setattr(
        service,
        "SQS_ORDER_PAID_QUEUE_URL",
        "http://localhost:9324/000000000000/order-paid"
    )

    monkeypatch.setattr(
        service,
        "SQS_ORDER_INVOICED_QUEUE_URL",
        "http://localhost:9324/000000000000/order-invoiced"
    )

    monkeypatch.setattr(
        service,
        "SQS_ORDER_REFUNDED_QUEUE_URL",
        "http://localhost:9324/000000000000/order-refunded"
    )

    send_message_mock = MagicMock()

    monkeypatch.setattr(
        service,
        "send_message",
        send_message_mock
    )

    return {
        "table": table,
        "send_message": send_message_mock,
    }


@pytest.fixture
def pending_event():
    return {
        "event_id": "event-001",
        "event_type": "ORDER_CREATED",
        "payload": '{"order_id": "order-001"}',
        "status": "PENDING",
    }


def test_publish_pending_events_success(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    mocks["table"].query.return_value = {
        "Items": [pending_event]
    }

    result = service.publish_pending_events()

    assert result == 1

    mocks["send_message"].assert_called_once_with(
        queue_url=service.SQS_ORDER_CREATED_QUEUE_URL,
        message_body=pending_event["payload"]
    )

    mocks["table"].update_item.assert_called_once()

    update = mocks["table"].update_item.call_args.kwargs

    assert update["Key"] == {"event_id": "event-001"}
    assert update["ExpressionAttributeValues"][":status"] == "PUBLISHED"
    assert update["ExpressionAttributeValues"][":published_at"]


def test_publish_pending_events_empty_queue(dynamodb_mocks):
    mocks = dynamodb_mocks

    mocks["table"].query.return_value = {
        "Items": []
    }

    result = service.publish_pending_events()

    assert result == 0

    mocks["send_message"].assert_not_called()
    mocks["table"].update_item.assert_not_called()


@pytest.mark.parametrize(
    ("event_type", "queue_attribute"),
    [
        ("ORDER_CREATED", "SQS_ORDER_CREATED_QUEUE_URL"),
        ("ORDER_RESERVED", "SQS_ORDER_RESERVED_QUEUE_URL"),
        ("ORDER_PAID", "SQS_ORDER_PAID_QUEUE_URL"),
        ("ORDER_INVOICED", "SQS_ORDER_INVOICED_QUEUE_URL"),
        ("ORDER_REFUNDED", "SQS_ORDER_REFUNDED_QUEUE_URL"),
    ]
)
def test_publish_pending_events_correct_queue(
    dynamodb_mocks,
    pending_event,
    event_type,
    queue_attribute
):
    mocks = dynamodb_mocks

    event = {
        **pending_event,
        "event_type": event_type,
    }

    mocks["table"].query.return_value = {
        "Items": [event]
    }

    result = service.publish_pending_events()

    assert result == 1

    mocks["send_message"].assert_called_once_with(
        queue_url=getattr(service, queue_attribute),
        message_body=event["payload"]
    )


def test_publish_pending_events_unsupported_type(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    event = {
        **pending_event,
        "event_type": "UNKNOWN_EVENT",
    }

    mocks["table"].query.return_value = {
        "Items": [event]
    }

    result = service.publish_pending_events()

    assert result == 0

    mocks["send_message"].assert_not_called()
    mocks["table"].update_item.assert_not_called()


def test_publish_pending_events_pagination(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    second_event = {
        **pending_event,
        "event_id": "event-002",
        "payload": '{"order_id": "order-002"}',
    }

    mocks["table"].query.side_effect = [
        {
            "Items": [pending_event],
            "LastEvaluatedKey": {
                "event_id": "event-001"
            },
        },
        {
            "Items": [second_event]
        },
    ]

    result = service.publish_pending_events()

    assert result == 2
    assert mocks["table"].query.call_count == 2
    assert mocks["send_message"].call_count == 2
    assert mocks["table"].update_item.call_count == 2

    second_query = mocks["table"].query.call_args_list[1]

    assert second_query.kwargs["ExclusiveStartKey"] == {
        "event_id": "event-001"
    }


def test_publish_pending_events_send_failure(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    mocks["table"].query.return_value = {
        "Items": [pending_event]
    }

    mocks["send_message"].side_effect = Exception(
        "SQS unavailable"
    )

    result = service.publish_pending_events()

    assert result == 0

    mocks["send_message"].assert_called_once()
    mocks["table"].update_item.assert_not_called()


def test_publish_pending_events_update_failure(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    mocks["table"].query.return_value = {
        "Items": [pending_event]
    }

    mocks["table"].update_item.side_effect = Exception(
        "DynamoDB unavailable"
    )

    result = service.publish_pending_events()

    assert result == 0

    mocks["send_message"].assert_called_once()
    mocks["table"].update_item.assert_called_once()


def test_publish_pending_events_continues_after_failure(
    dynamodb_mocks, pending_event
):
    mocks = dynamodb_mocks

    second_event = {
        **pending_event,
        "event_id": "event-002",
        "payload": '{"order_id": "order-002"}',
    }

    mocks["table"].query.return_value = {
        "Items": [pending_event, second_event]
    }

    mocks["send_message"].side_effect = [
        Exception("SQS unavailable"),
        None,
    ]

    result = service.publish_pending_events()

    assert result == 1
    assert mocks["send_message"].call_count == 2
    assert mocks["table"].update_item.call_count == 1

    update = mocks["table"].update_item.call_args.kwargs

    assert update["Key"] == {"event_id": "event-002"}