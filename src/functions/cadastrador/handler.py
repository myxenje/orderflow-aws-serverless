import json
from src.functions.cadastrador.service import (create_order, request_refund)


def lambda_handler(event, context):
    try:
        http_method = event.get("requestContext", {}).get(
            "http", {}
        ).get("method", "POST")

        path = event.get("rawPath", "")

        # POST /orders/{order_id}/refund
        if path.endswith("/refund") and http_method == "POST":
            order_id = event.get("pathParameters", {}).get("order_id")

            result = request_refund(order_id)

            return {
                "statusCode": 202,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(result, default=str)
            }

        # POST /orders
        body = event.get("body", event)

        if isinstance(body, str):
            body = json.loads(body)

        if not isinstance(body, dict):
            raise ValueError("O corpo da requisição deve ser um objeto JSON.")

        order = create_order(body)

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(order, default=str)
        }

    except (ValueError, json.JSONDecodeError) as error:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(error)})
        }

    except Exception as error:
        print(f"Erro no Cadastrador: {str(error)}")

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Erro interno ao processar a requisição."
            })
        }