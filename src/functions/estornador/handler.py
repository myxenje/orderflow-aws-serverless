import json
from src.functions.estornador.service import process_refund


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

            process_refund(body)

        except Exception as error:
            print(
                f"Erro ao processar mensagem {message_id}: {str(error)}"
            )

            batch_item_failures.append({
                "itemIdentifier": message_id
            })

    return {
        "batchItemFailures": batch_item_failures
    }