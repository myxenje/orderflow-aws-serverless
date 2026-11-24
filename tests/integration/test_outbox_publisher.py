from unittest.mock import MagicMock, patch
from uuid import uuid4
from src.functions.coletor.service import publish_pending_events
from src.shared.config.settings import (SQS_ORDER_CREATED_QUEUE_URL, SQS_ORDER_RESERVED_QUEUE_URL, SQS_ORDER_PAID_QUEUE_URL, SQS_ORDER_INVOICED_QUEUE_URL,)


def test_publish_pending_events():
    test_id = str(uuid4())

    events = [
        {
            "event_id": f"{test_id}-created",
            "event_type": "ORDER_CREATED",
            "payload": '{"event_type": "ORDER_CREATED"}',
            "status": "PENDING",
            "created_at": "2026-11-24T12:00:00+00:00"
        },
        {
            "event_id": f"{test_id}-reserved",
            "event_type": "ORDER_RESERVED",
            "payload": '{"event_type": "ORDER_RESERVED"}',
            "status": "PENDING",
            "created_at": "2026-11-24T12:01:00+00:00"
        },
        {
            "event_id": f"{test_id}-paid",
            "event_type": "ORDER_PAID",
            "payload": '{"event_type": "ORDER_PAID"}',
            "status": "PENDING",
            "created_at": "2026-11-24T12:02:00+00:00"
        },
        {
            "event_id": f"{test_id}-invoiced",
            "event_type": "ORDER_INVOICED",
            "payload": '{"event_type": "ORDER_INVOICED"}',
            "status": "PENDING",
            "created_at": "2026-11-24T12:03:00+00:00"
        }
    ]

    # 1. Cria um DynamoDB simulado
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()

    mock_dynamodb.Table.return_value = mock_table

    mock_table.query.return_value = {
        "Items": events
    }

    # 2. Executa o publicador com dependências simuladas
    with patch(
        "src.functions.coletor.service.get_dynamodb_resource",
        return_value=mock_dynamodb
    ), patch(
        "src.functions.coletor.service.send_message"
    ) as mock_send_message:

        published_count = publish_pending_events()

    # 3. Verifica a quantidade de eventos publicados
    assert published_count == 4

    # 4. Valida o roteamento dos quatro eventos
    expected_routes = {
        events[0]["payload"]: SQS_ORDER_CREATED_QUEUE_URL,
        events[1]["payload"]: SQS_ORDER_RESERVED_QUEUE_URL,
        events[2]["payload"]: SQS_ORDER_PAID_QUEUE_URL,
        events[3]["payload"]: SQS_ORDER_INVOICED_QUEUE_URL,
    }

    assert mock_send_message.call_count == 4

    for payload, expected_queue in expected_routes.items():
        assert any(
            call.kwargs["message_body"] == payload
            and call.kwargs["queue_url"] == expected_queue
            for call in mock_send_message.call_args_list
        ), f"Evento não foi enviado para a fila correta: {expected_queue}"

    # 5. Verifica a atualização dos quatro eventos
    assert mock_table.update_item.call_count == 4

    updated_event_ids = {
        call.kwargs["Key"]["event_id"]
        for call in mock_table.update_item.call_args_list
    }

    expected_event_ids = {
        event["event_id"]
        for event in events
    }

    assert updated_event_ids == expected_event_ids

    for call in mock_table.update_item.call_args_list:
        assert call.kwargs["ExpressionAttributeValues"][":status"] == "PUBLISHED"
        assert ":published_at" in call.kwargs["ExpressionAttributeValues"]