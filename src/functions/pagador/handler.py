import json
from src.functions.pagador.service import process_payment


def lambda_handler(event, context):
    records = event.get("Records", [])

    batch_item_failures = []

    for record in records:
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

            process_payment(body)

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