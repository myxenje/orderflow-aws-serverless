import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

IS_LOCAL = ENVIRONMENT == "development"

DYNAMODB_ENDPOINT = (
    os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    if IS_LOCAL
    else None
)

AWS_ACCESS_KEY_ID = (
    os.getenv("AWS_ACCESS_KEY_ID", "local")
    if IS_LOCAL
    else None
)

AWS_SECRET_ACCESS_KEY = (
    os.getenv("AWS_SECRET_ACCESS_KEY", "local")
    if IS_LOCAL
    else None
)

SQS_ENDPOINT = (
    "http://localhost:9324"
    if IS_LOCAL
    else None
)

SQS_ORDER_CREATED_QUEUE_URL = os.getenv(
    "SQS_ORDER_CREATED_QUEUE_URL"
)

SQS_ORDER_RESERVED_QUEUE_URL = os.getenv(
    "SQS_ORDER_RESERVED_QUEUE_URL"
)

SQS_ORDER_PAID_QUEUE_URL = os.getenv(
    "SQS_ORDER_PAID_QUEUE_URL"
)

SQS_ORDER_INVOICED_QUEUE_URL = os.getenv(
    "SQS_ORDER_INVOICED_QUEUE_URL"
)

SQS_ORDER_REFUND_REQUESTED_QUEUE_URL = os.getenv(
    "SQS_ORDER_REFUND_REQUESTED_QUEUE_URL"
)

SQS_ORDER_REFUNDED_QUEUE_URL = os.getenv(
    "SQS_ORDER_REFUNDED_QUEUE_URL"
)

SQS_ORDER_FAILURE_QUEUE_URL = os.getenv(
    "SQS_ORDER_FAILURE_QUEUE_URL"
)