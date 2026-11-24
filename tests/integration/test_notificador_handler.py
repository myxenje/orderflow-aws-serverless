import json
from unittest.mock import patch
from src.functions.notificador.handler import lambda_handler


def create_sqs_record(message_id, body):
    return {
        "messageId": message_id,
        "body": json.dumps(body),
    }


def test_lambda_handler_success():
    event = {
        "Records": [
            create_sqs_record(
                "message-1",
                {
                    "event_id": "event-123",
                    "event_type": "ORDER_INVOICED",
                    "order_id": "order-123",
                    "customer_id": "customer-123",
                    "invoice_id": "invoice-123",
                },
            )
        ]
    }

    with patch(
        "src.functions.notificador.handler.notify_customer"
    ) as mock_notify:

        result = lambda_handler(event, None)

    mock_notify.assert_called_once()

    assert result == {
        "batchItemFailures": []
    }


def test_lambda_handler_invalid_event():
    event = {
        "Records": [
            create_sqs_record(
                "message-2",
                {
                    "event_id": "event-123",
                    "event_type": "ORDER_PAID",
                },
            )
        ]
    }

    with patch(
        "src.functions.notificador.handler.notify_customer",
        side_effect=ValueError("Evento inválido"),
    ):

        result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-2"}
        ]
    }


def test_lambda_handler_invalid_json():
    event = {
        "Records": [
            {
                "messageId": "message-3",
                "body": "{json-invalido",
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-3"}
        ]
    }


def test_lambda_handler_partial_failure():
    event = {
        "Records": [
            create_sqs_record(
                "message-1",
                {"event_id": "event-1"},
            ),
            create_sqs_record(
                "message-2",
                {"event_id": "event-2"},
            ),
        ]
    }

    def notify_side_effect(body):
        if body["event_id"] == "event-2":
            raise ValueError("Falha simulada")

    with patch(
        "src.functions.notificador.handler.notify_customer",
        side_effect=notify_side_effect,
    ):

        result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-2"}
        ]
    }