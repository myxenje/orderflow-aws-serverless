from uuid import uuid4
from src.shared.events.idempotency import mark_event_as_processed


def test_event_is_processed_only_once():
    consumer_name = "reservador"
    event_id = str(uuid4())

    first_attempt = mark_event_as_processed(
        consumer_name,
        event_id
    )

    second_attempt = mark_event_as_processed(
        consumer_name,
        event_id
    )

    assert first_attempt is True
    assert second_attempt is False


def test_different_consumers_can_process_same_event():
    event_id = str(uuid4())

    reservador_result = mark_event_as_processed(
        "reservador",
        event_id
    )

    pagador_result = mark_event_as_processed(
        "pagador",
        event_id
    )

    assert reservador_result is True
    assert pagador_result is True