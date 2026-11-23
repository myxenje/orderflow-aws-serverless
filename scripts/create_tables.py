from src.shared.database.dynamodb import get_dynamodb_resource


def create_orders_table():
    dynamodb = get_dynamodb_resource()

    # Verifica se a tabela já existe
    existing_tables = dynamodb.meta.client.list_tables()["TableNames"]

    if "Orders" in existing_tables:
        print("A tabela Orders já existe.")
        return

    # Cria a tabela
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

    # Aguarda a tabela ficar disponível
    table.wait_until_exists()

    print("Tabela Orders criada com sucesso!")


if __name__ == "__main__":
    create_orders_table()
