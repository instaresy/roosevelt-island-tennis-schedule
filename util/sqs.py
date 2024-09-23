import boto3
import logging
import json

# Initialize SQS client
sqs = boto3.client('sqs')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def send_to_sqs(account_info, court, start_time, stop_time, queue_url):
    message_body = {
        'account_info': account_info,
        'court': court,
        'start_time': start_time.isoformat(),
        'stop_time': stop_time.isoformat(),
    }
    
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        logger.info(f"Message sent to SQS: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send message to SQS: {e}")