import json
from src.shared.events.sqs import send_message
from src.shared.config.settings import SQS_ORDER_REFUND_REQUESTED_QUEUE_URL


def request_refund(order_id, payment_id):
    event = {
        "event_id": "refund-request-" + order_id,
        "event_type": "ORDER_REFUND_REQUESTED",
        "order_id": order_id,
        "payment_id": payment_id,
    }

    response = send_message(
        queue_url=SQS_ORDER_REFUND_REQUESTED_QUEUE_URL,
        message_body=json.dumps(event),
    )

    print("Solicitação de estorno enviada com sucesso!")
    print(f"Message ID: {response['MessageId']}")
    print(f"Pedido: {order_id}")

    return response


if __name__ == "__main__":
    order_id = input("Informe o ID do pedido: ").strip()
    payment_id = input("Informe o ID do pagamento: ").strip()

    if not order_id or not payment_id:
        raise ValueError("Order ID e Payment ID são obrigatórios.")

    request_refund(order_id, payment_id)