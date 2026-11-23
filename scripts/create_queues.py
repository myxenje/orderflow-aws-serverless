from src.shared.events.sqs import get_sqs_client


def create_order_processing_queue():
    sqs = get_sqs_client()

    queue_name = "order-processing"

    existing_queues = sqs.list_queues().get("QueueUrls", [])

    for queue_url in existing_queues:
        if queue_url.rstrip("/").endswith(f"/{queue_name}"):
            print(f"A fila {queue_name} já existe.")
            return queue_url

    response = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            "VisibilityTimeout": "60",
            "MessageRetentionPeriod": "345600",
            "ReceiveMessageWaitTimeSeconds": "20"
        }
    )

    queue_url = response["QueueUrl"]

    print(f"Fila {queue_name} criada com sucesso!")
    print(f"Queue URL: {queue_url}")

    return queue_url


if __name__ == "__main__":
    create_order_processing_queue()
