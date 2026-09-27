import logging
import smtplib

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Retrying cannot fix these: bad credentials or addresses the server refuses.
PERMANENT_SMTP_ERRORS = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
)


@shared_task(
    bind=True,
    autoretry_for=(OSError,),
    dont_autoretry_for=PERMANENT_SMTP_ERRORS,
    retry_backoff=True,
    max_retries=5,
)
def send_email(self, subject, body, recipients):
    """Send a plain-text email. Transient SMTP/network errors are retried with backoff."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return 0
    try:
        sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
    except PERMANENT_SMTP_ERRORS:
        logger.exception("Email %r to %s failed permanently; check SMTP settings", subject, recipients)
        raise
    logger.info("Sent email %r to %s", subject, recipients)
    return sent
