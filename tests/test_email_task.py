import smtplib
from unittest import mock

import pytest
from celery.exceptions import Retry

from apps.notifications.tasks import send_email


def test_sends_to_non_empty_recipients(mailoutbox):
    assert send_email.delay("Hi", "Body", ["a@example.com", ""]).get() == 1
    assert mailoutbox[0].to == ["a@example.com"]


def test_no_recipients_sends_nothing(mailoutbox):
    assert send_email.delay("Hi", "Body", []).get() == 0
    assert mailoutbox == []


def test_transient_errors_schedule_a_retry():
    # In eager mode Celery surfaces a scheduled retry as a Retry exception.
    with mock.patch("apps.notifications.tasks.send_mail", side_effect=ConnectionResetError()):
        with pytest.raises(Retry):
            send_email.delay("Hi", "Body", ["a@example.com"]).get()


def test_bad_credentials_are_not_retried():
    error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with mock.patch("apps.notifications.tasks.send_mail", side_effect=error) as send:
        with pytest.raises(smtplib.SMTPAuthenticationError):
            send_email.delay("Hi", "Body", ["a@example.com"]).get()
    assert send.call_count == 1
