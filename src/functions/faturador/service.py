import json
from uuid import uuid4
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from src.shared.database.dynamodb import (
    get_dynamodb_resource,
    get_dynamodb_client,
)


def generate_invoice(event):
    event_id = event.get("event_id")
    order_id = event.get("order_id")

    if not event_id:
        raise ValueError("event_id é obrigatório.")

    if not order_id:
        raise ValueError("order_id é obrigatório.")

    if event.get("event_type") != "ORDER_PAID":
        raise ValueError("Tipo de evento não suportado.")

    dynamodb = get_dynamodb_resource()

    invoices_table = dynamodb.Table("Invoices")
    processed_table = dynamodb.Table("ProcessedEvents")

    consumer_name = "faturador"
    consumer_event_id = f"{consumer_name}#{event_id}"

    # 1. Verifica se o evento já foi processado
    processed_response = processed_table.get_item(
        Key={"consumer_event_id": consumer_event_id}
    )

    if "Item" in processed_response:
        return {
            "message": "Evento já processado.",
            "status": "INVOICED",
            "invoice_id": processed_response["Item"].get("invoice_id")
        }

    # 2. Verifica se o pedido já possui uma fatura
    invoice_response = invoices_table.get_item(
        Key={"order_id": order_id}
    )

    if "Item" in invoice_response:
        raise ValueError("Pedido já possui uma fatura.")

    # 3. Valida os dados necessários para faturamento
    customer_id = event.get("customer_id")
    total_amount = event.get("total_amount")
    payment_id = event.get("payment_id")

    if not customer_id:
        raise ValueError("customer_id é obrigatório.")

    if total_amount is None:
        raise ValueError("total_amount é obrigatório.")

    if not payment_id:
        raise ValueError("payment_id é obrigatório.")

    created_at = datetime.now(timezone.utc).isoformat()

    # 4. Gera a fatura
    invoice_id = str(uuid4())

    invoice = {
        "invoice_id": invoice_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "payment_id": payment_id,
        "total_amount": str(total_amount),
        "status": "ISSUED",
        "created_at": created_at
    }

    # 5. Prepara o evento ORDER_INVOICED
    invoiced_event_id = str(uuid4())

    invoiced_event = {
        "event_id": invoiced_event_id,
        "event_type": "ORDER_INVOICED",
        "order_id": order_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "payment_id": payment_id,
        "total_amount": str(total_amount),
        "status": "INVOICED",
        "created_at": created_at
    }

    outbox_event = {
        "event_id": invoiced_event_id,
        "event_type": "ORDER_INVOICED",
        "payload": json.dumps(invoiced_event),
        "status": "PENDING",
        "created_at": created_at
    }

    client = get_dynamodb_client()

    # 6. Persiste a fatura, a idempotência
    # e o evento de saída atomicamente
    try:
        client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": "Invoices",
                        "Item": {
                            "order_id": {"S": order_id},
                            "invoice_id": {"S": invoice_id},
                            "customer_id": {"S": customer_id},
                            "payment_id": {"S": payment_id},
                            "total_amount": {
                                "S": str(total_amount)
                            },
                            "status": {"S": "ISSUED"},
                            "created_at": {"S": created_at}
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(order_id)"
                        )
                    }
                },
                {
                    "Put": {
                        "TableName": "ProcessedEvents",
                        "Item": {
                            "consumer_event_id": {
                                "S": consumer_event_id
                            },
                            "consumer_name": {
                                "S": consumer_name
                            },
                            "event_id": {"S": event_id},
                            "invoice_id": {"S": invoice_id},
                            "processed_at": {"S": created_at}
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(consumer_event_id)"
                        )
                    }
                },
                {
                    "Put": {
                        "TableName": "Outbox",
                        "Item": {
                            "event_id": {"S": invoiced_event_id},
                            "event_type": {"S": "ORDER_INVOICED"},
                            "payload": {
                                "S": json.dumps(invoiced_event)
                            },
                            "status": {"S": "PENDING"},
                            "created_at": {"S": created_at}
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(event_id)"
                        )
                    }
                }
            ]
        )

        return {
            "message": "Fatura gerada com sucesso.",
            "status": "INVOICED",
            "invoice_id": invoice_id
        }

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "TransactionCanceledException":

            # 7. Verifica se o mesmo evento já foi processado
            processed_response = processed_table.get_item(
                Key={"consumer_event_id": consumer_event_id}
            )

            if "Item" in processed_response:
                return {
                    "message": "Evento já processado.",
                    "status": "INVOICED",
                    "invoice_id": processed_response["Item"].get(
                        "invoice_id"
                    )
                }

            # 8. Verifica se outro evento já gerou a fatura
            latest_invoice = invoices_table.get_item(
                Key={"order_id": order_id}
            ).get("Item")

            if latest_invoice:
                raise ValueError(
                    "Pedido já possui uma fatura."
                ) from error

        raise