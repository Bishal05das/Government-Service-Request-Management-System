"""
Status workflow for service requests.

    SUBMITTED ──assign──▶ ASSIGNED ──▶ IN_PROGRESS ──▶ RESOLVED ──▶ CLOSED
        │                    │              │
        ├──▶ CANCELLED       └──────────────┴──▶ REJECTED
        └──▶ REJECTED

SUBMITTED -> ASSIGNED only happens through officer assignment, never through
a plain status change.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role

from .models import ServiceRequest, Status, StatusChange

OWNER = "owner"
ASSIGNED_OFFICER = "assigned_officer"
ADMIN = "admin"

TRANSITIONS = {
    (Status.SUBMITTED, Status.CANCELLED): {OWNER, ADMIN},
    (Status.SUBMITTED, Status.REJECTED): {ADMIN},
    (Status.ASSIGNED, Status.IN_PROGRESS): {ASSIGNED_OFFICER, ADMIN},
    (Status.ASSIGNED, Status.REJECTED): {ASSIGNED_OFFICER, ADMIN},
    (Status.IN_PROGRESS, Status.RESOLVED): {ASSIGNED_OFFICER, ADMIN},
    (Status.IN_PROGRESS, Status.REJECTED): {ASSIGNED_OFFICER, ADMIN},
    (Status.RESOLVED, Status.CLOSED): {OWNER, ADMIN},
}

NOTE_REQUIRED_FOR = {Status.REJECTED}


def actor_relations(service_request, user):
    """How the user relates to the request: owner, assigned officer and/or admin."""
    relations = set()
    if user.role == Role.ADMIN:
        relations.add(ADMIN)
    if user.role == Role.CITIZEN and service_request.citizen_id == user.pk:
        relations.add(OWNER)
    if user.role == Role.OFFICER and service_request.assigned_officer_id == user.pk:
        relations.add(ASSIGNED_OFFICER)
    return relations


def allowed_transitions(service_request, user):
    relations = actor_relations(service_request, user)
    return [
        to_status
        for (from_status, to_status), allowed in TRANSITIONS.items()
        if from_status == service_request.status and relations & allowed
    ]


def record_status_change(service_request, from_status, user, note=""):
    return StatusChange.objects.create(
        service_request=service_request,
        from_status=from_status,
        to_status=service_request.status,
        changed_by=user,
        note=note,
    )


@transaction.atomic
def change_status(service_request, new_status, user, note=""):
    # Lock the row so two concurrent transitions can't both succeed.
    service_request = ServiceRequest.objects.select_for_update().get(pk=service_request.pk)
    current = service_request.status

    allowed_roles = TRANSITIONS.get((current, new_status))
    if allowed_roles is None:
        raise ValidationError({"status": f"Cannot change status from {current} to {new_status}."})
    if not actor_relations(service_request, user) & allowed_roles:
        raise PermissionDenied(f"You are not allowed to move this request to {new_status}.")
    if new_status in NOTE_REQUIRED_FOR and not note.strip():
        raise ValidationError({"note": f"A note is required when moving to {new_status}."})

    service_request.status = new_status
    update_fields = ["status", "updated_at"]
    if new_status == Status.RESOLVED:
        service_request.resolved_at = timezone.now()
        update_fields.append("resolved_at")
    service_request.save(update_fields=update_fields)

    record_status_change(service_request, current, user, note)
    return service_request
