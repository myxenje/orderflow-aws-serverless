from src.shared.database.dynamodb import get_dynamodb_client

def test_dynamodb_connection():
    dynamodb = get_dynamodb_client()

    response = dynamodb.list_tables()

    assert "TableNames" in response