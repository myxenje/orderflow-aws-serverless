import boto3

from src.shared.config.settings import (
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
)

SQS_ENDPOINT = "http://localhost:9324"


def get_sqs_client():
    return boto3.client(
        "sqs",
        region_name=AWS_REGION,
        endpoint_url=SQS_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def send_message(queue_url, message_body):
    sqs = get_sqs_client()

    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body,
    )

    return response
