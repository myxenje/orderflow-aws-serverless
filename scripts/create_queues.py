from src.shared.events.sqs import get_sqs_client


def create_queue(queue_name):
    sqs = get_sqs_client()

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


def create_order_processing_queue():
    return create_queue("order-processing")


def create_order_reserved_queue():
    return create_queue("order-reserved")


def create_order_paid_queue():
    return create_queue("order-paid")


def create_order_invoiced_queue():
    return create_queue("order-invoiced")

def create_order_refund_requested_queue():
    return create_queue("order-refund-requested")

def create_order_refunded_queue():
    return create_queue("order-refunded")

if __name__ == "__main__":
    create_order_processing_queue()
    create_order_reserved_queue()
    create_order_paid_queue()
    create_order_invoiced_queue()
    create_order_refund_requested_queue()
    create_order_refunded_queue()