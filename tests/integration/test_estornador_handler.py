from unittest.mock import patch
from src.functions.estornador.handler import lambda_handler


@patch("src.functions.estornador.handler.process_refund")
def test_lambda_handler_success(mock_process_refund):
    event = {
        "Records": [
            {
                "messageId": "message-001",
                "body": (
                    '{"event_id": "event-001", '
                    '"event_type": "ORDER_REFUND_REQUESTED", '
                    '"order_id": "order-001", '
                    '"payment_id": "payment-001"}'
                )
            }
        ]
    }

    result = lambda_handler(event, None)

    mock_process_refund.assert_called_once_with({
        "event_id": "event-001",
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": "order-001",
        "payment_id": "payment-001"
    })

    assert result == {"batchItemFailures": []}

@patch("src.functions.estornador.handler.process_refund")
def test_lambda_handler_invalid_event(mock_process_refund):
    mock_process_refund.side_effect = ValueError(
        "Pedido não está disponível para estorno."
    )

    event = {
        "Records": [
            {
                "messageId": "message-002",
                "body": (
                    '{"event_id": "event-002", '
                    '"event_type": "ORDER_REFUND_REQUESTED", '
                    '"order_id": "order-002", '
                    '"payment_id": "payment-002"}'
                )
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-002"}
        ]
    }

    mock_process_refund.assert_called_once()


@patch("src.functions.estornador.handler.process_refund")
def test_lambda_handler_invalid_json(mock_process_refund):
    event = {
        "Records": [
            {
                "messageId": "message-003",
                "body": "{json-invalido"
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-003"}
        ]
    }

    mock_process_refund.assert_not_called()

@patch("src.functions.estornador.handler.process_refund")
def test_lambda_handler_partial_failure(mock_process_refund):
    mock_process_refund.side_effect = [
        None,
        ValueError("Falha ao processar estorno."),
        None
    ]

    event = {
        "Records": [
            {
                "messageId": "message-001",
                "body": '{"event_id": "event-001"}'
            },
            {
                "messageId": "message-002",
                "body": '{"event_id": "event-002"}'
            },
            {
                "messageId": "message-003",
                "body": '{"event_id": "event-003"}'
            }
        ]
    }

    result = lambda_handler(event, None)

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "message-002"}
        ]
    }

    assert mock_process_refund.call_count == 3

