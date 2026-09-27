import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def send_email(self, subject, body, recipients):
    """Send a plain-text email. Retried with backoff on SMTP/network errors."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return 0
    sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
    logger.info("Sent email %r to %s", subject, recipients)
    return sent
