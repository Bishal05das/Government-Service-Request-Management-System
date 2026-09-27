"""Email notifications for people involved in a service request."""
from apps.notifications.services import queue_email


def _others(service_request, actor):
    """Citizen and assigned officer, minus whoever triggered the event."""
    people = [service_request.citizen, service_request.assigned_officer]
    return [p.email for p in people if p is not None and p.pk != actor.pk and p.is_active]


def _subject(service_request, text):
    return f"[Request #{service_request.pk}] {text}"


def notify_officer_assigned(service_request, actor):
    officer = service_request.assigned_officer
    queue_email(
        _subject(service_request, "Assigned to you"),
        f"Request #{service_request.pk} \"{service_request.title}\" "
        f"({service_request.get_priority_display()} priority) has been assigned to you.\n",
        [officer.email],
    )
    queue_email(
        _subject(service_request, "Officer assigned"),
        f"Your request \"{service_request.title}\" has been assigned to an officer "
        f"and is now {service_request.get_status_display()}.\n",
        [service_request.citizen.email],
    )


def notify_status_changed(service_request, from_status, actor, note=""):
    body = (
        f"Request #{service_request.pk} \"{service_request.title}\" changed from "
        f"{from_status} to {service_request.status}.\n"
    )
    if note:
        body += f"\nNote: {note}\n"
    queue_email(
        _subject(service_request, f"Status changed to {service_request.get_status_display()}"),
        body,
        _others(service_request, actor),
    )


def notify_new_comment(comment):
    service_request = comment.service_request
    author = comment.author
    queue_email(
        _subject(service_request, "New comment"),
        f"{author.get_full_name() or author.email} commented on request #{service_request.pk}:\n\n"
        f"{comment.body}\n",
        _others(service_request, author),
    )
