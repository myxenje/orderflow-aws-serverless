from src.shared.events.sqs import get_sqs_client
from src.shared.config.settings import SQS_ORDER_INVOICED_QUEUE_URL
from src.functions.notificador.handler import lambda_handler


def consume_notifications():
    sqs = get_sqs_client()

    response = sqs.receive_message(
        QueueUrl=SQS_ORDER_INVOICED_QUEUE_URL,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=5,
        VisibilityTimeout=60,
    )

    messages = response.get("Messages", [])

    if not messages:
        print("Nenhuma notificação disponível.")
        return

    print(f"Mensagens recebidas: {len(messages)}")

    # Converte o formato retornado pelo SQS
    # para o formato esperado pelo Lambda
    records = [
        {
            "messageId": message["MessageId"],
            "body": message["Body"],
            "receiptHandle": message["ReceiptHandle"],
        }
        for message in messages
    ]

    result = lambda_handler(
        {"Records": records},
        None,
    )

    failed_message_ids = {
        item["itemIdentifier"]
        for item in result["batchItemFailures"]
    }

    deleted_count = 0
    failed_count = 0

    for message in messages:
        if message["MessageId"] in failed_message_ids:
            failed_count += 1
            continue

        sqs.delete_message(
            QueueUrl=SQS_ORDER_INVOICED_QUEUE_URL,
            ReceiptHandle=message["ReceiptHandle"],
        )

        deleted_count += 1

    print(f"Mensagens excluídas: {deleted_count}")
    print(f"Mensagens com falha: {failed_count}")


if __name__ == "__main__":
    consume_notifications()