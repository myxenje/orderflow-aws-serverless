import json
from src.functions.cadastrador.service import create_order


def lambda_handler(event, context):
    try:
        # Extrai o corpo da requisição
        body = event.get("body", event)

        if isinstance(body, str):
            body = json.loads(body)

        if not isinstance(body, dict):
            raise ValueError("O corpo da requisição deve ser um objeto JSON.")

        # Cria pediido
        order = create_order(body)

        # Retorna Resposta HTTP
        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(order, default=str)
        }

    except (ValueError, json.JSONDecodeError) as error:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": str(error)
            })
        }

    except Exception:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Erro interno ao cadastrar pedido."
            })
        }