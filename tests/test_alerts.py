from docket import alerts


class FakeSns:
    def __init__(self):
        self.published = []

    def publish(self, **kwargs):
        self.published.append(kwargs)


def test_publish_alert_sends_subject_and_message(monkeypatch):
    sns = FakeSns()
    monkeypatch.setattr(alerts.boto3, "client", lambda service: sns)

    alerts.publish_alert("arn:aws:sns:us-east-2:1:docket", "s" * 120, "body")

    assert sns.published == [
        {
            "TopicArn": "arn:aws:sns:us-east-2:1:docket",
            "Subject": "s" * 100,
            "Message": "body",
        }
    ]
