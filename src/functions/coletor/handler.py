from src.functions.coletor.service import publish_pending_events

def lambda_handler(event, context):
    try:
        published_count = publish_pending_events()

        return {
            "statusCode": 200,
            "body": {
                "message": "Eventos pendentes processados.",
                "published_count": published_count
            }
        }

    except Exception as error:
        print(f"Erro no Coletor: {str(error)}")
        raise