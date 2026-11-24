from unittest.mock import patch
from uuid import uuid4
from src.functions.coletor.service import publish_pending_events
from src.shared.database.dynamodb import get_dynamodb_resource
from src.shared.config.settings import (
    SQS_ORDER_CREATED_QUEUE_URL,
    SQS_ORDER_RESERVED_QUEUE_URL,
)


@patch("src.functions.coletor.service.send_message")
def test_publish_pending_events(mock_send_message):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("Outbox")

    test_id = str(uuid4())

    events = [
        {
            "event_id": f"{test_id}-created",
            "event_type": "ORDER_CREATED",
            "payload": (
                '{"event_type": "ORDER_CREATED", '
                '"order_id": "test-order-created"}'
            ),
            "status": "PENDING",
            "created_at": "2026-11-24T12:00:00+00:00"
        },
        {
            "event_id": f"{test_id}-reserved",
            "event_type": "ORDER_RESERVED",
            "payload": (
                '{"event_type": "ORDER_RESERVED", '
                '"order_id": "test-order-reserved"}'
            ),
            "status": "PENDING",
            "created_at": "2026-11-24T12:01:00+00:00"
        }
    ]

    # 1. Insere os dois eventos na Outbox
    for event in events:
        table.put_item(Item=event)

    # 2. Executa o publicador
    published_count = publish_pending_events()

    assert published_count >= 2

    # 3. Valida o roteamento dos eventos para as filas
    calls = mock_send_message.call_args_list

    expected_routes = {
        events[0]["payload"]: SQS_ORDER_CREATED_QUEUE_URL,
        events[1]["payload"]: SQS_ORDER_RESERVED_QUEUE_URL,
    }

    for payload, expected_queue in expected_routes.items():
        assert any(
            call.kwargs["message_body"] == payload
            and call.kwargs["queue_url"] == expected_queue
            for call in calls
        ), f"Evento não foi enviado para a fila correta: {expected_queue}"

    # 4. Verifica se os dois eventos foram atualizados no DynamoDB
    for event in events:
        response = table.get_item(
            Key={"event_id": event["event_id"]}
        )

        saved_event = response["Item"]

        assert saved_event["status"] == "PUBLISHED"
        assert "published_at" in saved_event