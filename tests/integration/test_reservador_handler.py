import json
from uuid import uuid4
from unittest.mock import patch
from src.functions.reservador.handler import lambda_handler
from src.functions.cadastrador.service import create_order


def test_lambda_handler_success():
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-001",
                "quantity": 2,
                "unit_price": "50.00"
            }
        ]
    })

    event = {
        "Records": [
            {
                "messageId": "message-001",
                "body": json.dumps({
                    "event_id": str(uuid4()),
                    "event_type": "ORDER_CREATED",
                    "order_id": order["order_id"]
                })
            }
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []


def test_lambda_handler_invalid_event():
    event = {
        "Records": [
            {
                "messageId": "message-002",
                "body": json.dumps({
                    "event_type": "PAYMENT_COMPLETED"
                })
            }
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == [
        {"itemIdentifier": "message-002"}
    ]


def test_lambda_handler_partial_batch_failure():
    order = create_order({
        "customer_id": f"customer-{uuid4()}",
        "items": [
            {
                "product_id": "product-002",
                "quantity": 1,
                "unit_price": "75.00"
            }
        ]
    })

    event = {
        "Records": [
            {
                "messageId": "message-success",
                "body": json.dumps({
                    "event_id": str(uuid4()),
                    "event_type": "ORDER_CREATED",
                    "order_id": order["order_id"]
                })
            },
            {
                "messageId": "message-failure",
                "body": json.dumps({
                    "event_type": "PAYMENT_COMPLETED"
                })
            }
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == [
        {"itemIdentifier": "message-failure"}
    ]