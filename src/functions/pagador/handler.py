import json
from src.functions.pagador.service import (process_payment, publish_payment_failure,)


def lambda_handler(event, context):
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            body = json.loads(record["body"])

            if not isinstance(body, dict):
                raise ValueError(
                    "O corpo da mensagem deve ser um objeto JSON."
                )

            if body.get("event_type") != "ORDER_RESERVED":
                raise ValueError(
                    "Tipo de evento não suportado."
                )

            try:
                process_payment(body)

            except Exception as error:
                print(
                    f"Falha no pagamento do pedido "
                    f"{body.get('order_id')}: {error}"
                )

                publish_payment_failure(body, error)

        except Exception as error:
            print(
                f"Erro ao processar mensagem {message_id}: {error}"
            )

            batch_item_failures.append({
                "itemIdentifier": message_id
            })

    return {
        "batchItemFailures": batch_item_failures
    }