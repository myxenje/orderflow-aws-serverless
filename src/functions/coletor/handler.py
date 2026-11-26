from src.functions.coletor.service import publish_stream_events


def lambda_handler(event, context):
    batch_item_failures = []

    for record in event.get("Records", []):
        try:
            publish_stream_events(record)

        except Exception as error:
            sequence_number = record.get(
                "dynamodb", {}
            ).get("SequenceNumber")

            print(
                f"Erro ao processar registro "
                f"{sequence_number}: {str(error)}"
            )

            if sequence_number:
                batch_item_failures.append({
                    "itemIdentifier": sequence_number
                })
            else:
                raise

    return {
        "batchItemFailures": batch_item_failures
    }