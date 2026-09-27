from django.db import transaction

from .tasks import send_email


def queue_email(subject, body, recipients):
    """Queue an email once the surrounding transaction commits, so we never mail about rolled-back work."""
    recipients = list(recipients)
    transaction.on_commit(lambda: send_email.delay(subject, body, recipients))
