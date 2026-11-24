import json
from src.functions.cadastrador.handler import lambda_handler


def test_lambda_handler_success():
    event = {
        "body": json.dumps({
            "customer_id": "customer-002",
            "items": [
                {
                    "product_id": "product-001",
                    "quantity": 2,
                    "unit_price": "50.00"
                }
            ]
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 201

    body = json.loads(response["body"])

    assert body["customer_id"] == "customer-002"
    assert body["status"] == "PENDING"
    assert body["total_amount"] == "100.00"


def test_lambda_handler_invalid_data():
    event = {
        "body": json.dumps({
            "customer_id": "",
            "items": []
        })
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 400