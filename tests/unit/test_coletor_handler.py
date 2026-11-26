from unittest.mock import patch
from src.functions.coletor.handler import lambda_handler


@patch("src.functions.coletor.handler.publish_stream_events")
def test_lambda_handler_success(mock_publish):
    event = {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {
                    "SequenceNumber": "100",
                },
            }
        ]
    }

    response = lambda_handler(event, None)

    assert response == {"batchItemFailures": []}
    mock_publish.assert_called_once_with(event["Records"][0])


@patch("src.functions.coletor.handler.publish_stream_events")
def test_lambda_handler_partial_failure(mock_publish):
    first_record = {
        "eventName": "INSERT",
        "dynamodb": {"SequenceNumber": "100"},
    }

    second_record = {
        "eventName": "INSERT",
        "dynamodb": {"SequenceNumber": "200"},
    }

    mock_publish.side_effect = [
        None,
        Exception("SQS unavailable"),
    ]

    response = lambda_handler({
        "Records": [first_record, second_record],
    }, None)

    assert response == {
        "batchItemFailures": [
            {"itemIdentifier": "200"}
        ]
    }

    assert mock_publish.call_count == 2


@patch("src.functions.coletor.handler.publish_stream_events")
def test_lambda_handler_without_sequence_number(mock_publish):
    mock_publish.side_effect = Exception("Erro")

    event = {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {},
            }
        ]
    }

    try:
        lambda_handler(event, None)
        assert False, "Era esperada uma exceção."
    except Exception as error:
        assert str(error) == "Erro"