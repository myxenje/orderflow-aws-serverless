import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

DYNAMODB_ENDPOINT = os.getenv(
    "DYNAMODB_ENDPOINT",
    "http://localhost:8000"
)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "local")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "local")

SQS_QUEUE_URL = os.getenv(
    "SQS_QUEUE_URL",
    "http://localhost:9324/000000000000/order-processing"
)
