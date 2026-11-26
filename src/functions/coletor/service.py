from boto3.dynamodb.types import TypeDeserializer
from src.shared.events.sqs import send_message
from src.shared.config.settings import SQS_ORDER_CREATED_QUEUE_URL


def publish_stream_events(record):
    """
    Recebe um evento INSERT do DynamoDB Streams
    e publica o pedido na fila order-processing.
    """

    if record.get("eventName") != "INSERT":
        return

    new_image = record.get("dynamodb", {}).get("NewImage")

    if not new_image:
        raise ValueError("Registro do Stream não possui NewImage.")

    deserializer = TypeDeserializer()

    event = {
        key: deserializer.deserialize(value)
        for key, value in new_image.items()
    }

    payload = event.get("payload")

    if not payload:
        raise ValueError("Payload não encontrado no evento da Outbox.")

    send_message(
        queue_url=SQS_ORDER_CREATED_QUEUE_URL,
        message_body=payload
    )

    print("Pedido publicado na fila order-processing com sucesso.")