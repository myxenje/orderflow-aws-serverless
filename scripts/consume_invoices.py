from src.shared.events.sqs import get_sqs_client
from src.shared.config.settings import SQS_ORDER_PAID_QUEUE_URL
from src.functions.faturador.handler import lambda_handler


def consume_invoice_messages():
    sqs = get_sqs_client()

    response = sqs.receive_message(
        QueueUrl=SQS_ORDER_PAID_QUEUE_URL,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=5,
        VisibilityTimeout=60
    )

    messages = response.get("Messages", [])

    if not messages:
        print("Nenhuma mensagem encontrada na fila.")
        return

    records = [
        {
            "messageId": message["MessageId"],
            "body": message["Body"]
        }
        for message in messages
    ]

    lambda_response = lambda_handler(
        {"Records": records},
        None
    )

    failed_message_ids = {
        failure["itemIdentifier"]
        for failure in lambda_response["batchItemFailures"]
    }

    deleted_count = 0

    for message in messages:
        if message["MessageId"] in failed_message_ids:
            print(
                f"Mensagem não processada: {message['MessageId']}"
            )
            continue

        sqs.delete_message(
            QueueUrl=SQS_ORDER_PAID_QUEUE_URL,
            ReceiptHandle=message["ReceiptHandle"]
        )

        deleted_count += 1

    print(f"Mensagens recebidas: {len(messages)}")
    print(f"Mensagens excluídas: {deleted_count}")
    print(f"Mensagens com falha: {len(failed_message_ids)}")


if __name__ == "__main__":
    consume_invoice_messages()