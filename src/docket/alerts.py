import boto3

from .config.logger import get_logger

logger = get_logger("alerts")

SUBJECT_LIMIT = 100


def publish_alert(topic_arn: str, subject: str, message: str) -> None:
    """
    Publish one message to an SNS topic.

    Args:
        topic_arn: the topic to publish to
        subject: email subject; SNS caps it at 100 characters, so it is cut
        message: the body, plain text

    Returns:
        None
    """
    boto3.client("sns").publish(
        TopicArn=topic_arn, Subject=subject[:SUBJECT_LIMIT], Message=message
    )
    logger.info("published alert to %s", topic_arn)
