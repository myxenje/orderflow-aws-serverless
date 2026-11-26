from datetime import datetime, timezone
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import get_dynamodb_resource
from src.shared.events.sns import publish_notification


def notify_customer(event):
    event_id = event.get("event_id")
    order_id = event.get("order_id")
    event_type = event.get("event_type")
    customer_id = event.get("customer_id")
    invoice_id = event.get("invoice_id")

    if not event_id:
        raise ValueError("event_id é obrigatório.")

    if not order_id:
        raise ValueError("order_id é obrigatório.")

    if event_type != "ORDER_INVOICED":
        raise ValueError("O evento deve ser do tipo ORDER_INVOICED.")

    if not customer_id:
        raise ValueError("customer_id é obrigatório.")

    if not invoice_id:
        raise ValueError("invoice_id é obrigatório.")

    dynamodb = get_dynamodb_resource()

    processed_events = dynamodb.Table("ProcessedEvents")

    consumer_event_id = f"notificador#{event_id}"

    existing_event = processed_events.get_item(
        Key={"consumer_event_id": consumer_event_id}
    ).get("Item")

    if existing_event:
        return {
            "status": "DUPLICATE",
            "message": "Notificação já processada.",
            "order_id": order_id,
        }

    notification = {
        "consumer_event_id": consumer_event_id,
        "consumer_name": "notificador",
        "event_id": event_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "status": "SENT",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        processed_events.put_item(
            Item=notification,
            ConditionExpression="attribute_not_exists(consumer_event_id)",
        )

    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {
                "status": "DUPLICATE",
                "message": "Notificação já processada.",
                "order_id": order_id,
            }

        raise

    subject = f"Pedido {order_id} faturado com sucesso"

    message = (
        f"Seu pedido foi faturado!\n\n"
        f"Pedido: {order_id}\n"
        f"Cliente: {customer_id}\n"
        f"Nota fiscal: {invoice_id}\n"
        f"Status: Faturado"
    )

    publish_notification(
        subject=subject,
        message=message,
    )

    print(
        f"Notificacao SNS publicada para o cliente "
        f"{customer_id}, pedido {order_id}."
    )
    
    return {
        "status": "SENT",
        "order_id": order_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
    }