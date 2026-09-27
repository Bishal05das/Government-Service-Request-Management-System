"""
Email verification using signed, time-limited tokens (no extra table needed).

The token embeds the user id and email, so it stops working if the email changes.
"""
from django.conf import settings
from django.core import signing
from django.urls import reverse

from apps.notifications.services import queue_email

from .models import User

SALT = "accounts.email-verification"


def make_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def user_from_token(token):
    """Return the user for a valid token, or None if it is invalid/expired/stale."""
    max_age = settings.EMAIL_VERIFICATION_TOKEN_HOURS * 3600
    try:
        payload = signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    return User.objects.filter(pk=payload.get("uid"), email=payload.get("email")).first()


def send_verification_email(user, request):
    link = request.build_absolute_uri(reverse("auth-verify-email")) + f"?token={make_token(user)}"
    body = (
        f"Hello {user.get_full_name() or user.email},\n\n"
        "Please confirm your email address to activate your account:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.EMAIL_VERIFICATION_TOKEN_HOURS} hours.\n"
    )
    queue_email("Verify your email address", body, [user.email])
