from src.shared.database.dynamodb import get_dynamodb_resource


def create_orders_table():
    dynamodb = get_dynamodb_resource()

    existing_tables = dynamodb.meta.client.list_tables()["TableNames"]

    if "Orders" in existing_tables:
        print("A tabela Orders já existe.")
        return

    table = dynamodb.create_table(
        TableName="Orders",
        KeySchema=[
            {
                "AttributeName": "order_id",
                "KeyType": "HASH"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "order_id",
                "AttributeType": "S"
            }
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    table.wait_until_exists()

    print("Tabela Orders criada com sucesso!")


def create_outbox_table():
    dynamodb = get_dynamodb_resource()

    existing_tables = dynamodb.meta.client.list_tables()["TableNames"]

    if "Outbox" in existing_tables:
        print("A tabela Outbox já existe.")
        return

    table = dynamodb.create_table(
        TableName="Outbox",
        KeySchema=[
            {
                "AttributeName": "event_id",
                "KeyType": "HASH"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "event_id",
                "AttributeType": "S"
            },
            {
                "AttributeName": "status",
                "AttributeType": "S"
            },
            {
                "AttributeName": "created_at",
                "AttributeType": "S"
            }
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "StatusCreatedAtIndex",
                "KeySchema": [
                    {
                        "AttributeName": "status",
                        "KeyType": "HASH"
                    },
                    {
                        "AttributeName": "created_at",
                        "KeyType": "RANGE"
                    }
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                }
            }
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    table.wait_until_exists()

    print("Tabela Outbox criada com sucesso!")

def create_processed_events_table():
    dynamodb = get_dynamodb_resource()

    existing_tables = dynamodb.meta.client.list_tables()["TableNames"]

    if "ProcessedEvents" in existing_tables:
        print("A tabela ProcessedEvents já existe.")
        return

    dynamodb.create_table(
        TableName="ProcessedEvents",
        KeySchema=[
            {
                "AttributeName": "consumer_event_id",
                "KeyType": "HASH"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "consumer_event_id",
                "AttributeType": "S"
            }
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    print("Tabela ProcessedEvents criada com sucesso!")

if __name__ == "__main__":
    create_orders_table()
    create_outbox_table()
    create_processed_events_table()