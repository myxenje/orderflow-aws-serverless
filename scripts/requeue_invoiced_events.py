from src.shared.database.dynamodb import get_dynamodb_resource

EVENT_IDS = [
    "e8d7690d-ae44-4a0b-8b2b-0e4132fd5c57",
    "777477ee-abd2-4ab4-89d5-2e7962677b14",
    "dbb6cd11-3cf2-4356-bd7d-e1e63cbc6274",
    "227c9ff6-5edd-4e4a-af55-1131601f81f7",
]


def main():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("Outbox")

    for event_id in EVENT_IDS:
        table.update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET #status = :pending REMOVE published_at",
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":pending": "PENDING"
            },
        )

        print(f"Evento reprocessável: {event_id}")

    print("\nQuatro eventos preparados para republicação.")


if __name__ == "__main__":
    main()