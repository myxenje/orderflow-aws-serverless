import json
from src.functions.faturador.service import generate_invoice


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

            if body.get("event_type") != "ORDER_PAID":
                raise ValueError(
                    "Tipo de evento não suportado."
                )

            generate_invoice(body)

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