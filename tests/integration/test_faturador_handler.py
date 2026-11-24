from unittest.mock import patch
from src.functions.faturador.handler import lambda_handler


def test_handler_processes_valid_order_paid_event():
    event_body = {
        "event_id": "event-123",
        "event_type": "ORDER_PAID",
        "order_id": "order-123",
        "customer_id": "customer-123",
        "payment_id": "payment-123",
        "total_amount": "100.00"
    }

    event = {
        "Records": [
            {
                "messageId": "message-123",
                "body": __import__("json").dumps(event_body)
            }
        ]
    }

    with patch(
        "src.functions.faturador.handler.generate_invoice"
    ) as mock_generate_invoice:

        response = lambda_handler(event, None)

    mock_generate_invoice.assert_called_once_with(event_body)
    assert response["batchItemFailures"] == []


def test_handler_returns_failure_for_invalid_event_type():
    event_body = {
        "event_id": "event-123",
        "event_type": "ORDER_CREATED",
        "order_id": "order-123"
    }

    event = {
        "Records": [
            {
                "messageId": "message-456",
                "body": __import__("json").dumps(event_body)
            }
        ]
    }

    with patch(
        "src.functions.faturador.handler.generate_invoice"
    ) as mock_generate_invoice:

        response = lambda_handler(event, None)

    mock_generate_invoice.assert_not_called()

    assert response["batchItemFailures"] == [
        {"itemIdentifier": "message-456"}
    ]


def test_handler_returns_failure_for_invalid_json():
    event = {
        "Records": [
            {
                "messageId": "message-789",
                "body": "{json inválido"
            }
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == [
        {"itemIdentifier": "message-789"}
    ]