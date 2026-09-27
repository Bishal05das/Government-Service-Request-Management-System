from django.db.models import Case, IntegerField, Value, When

from apps.accounts.models import Role

from .models import Priority, ServiceRequest

PRIORITY_RANK = Case(
    When(priority=Priority.LOW, then=Value(1)),
    When(priority=Priority.MEDIUM, then=Value(2)),
    When(priority=Priority.HIGH, then=Value(3)),
    When(priority=Priority.URGENT, then=Value(4)),
    output_field=IntegerField(),
)


def visible_requests_for(user):
    """
    Requests a user may see:
    citizens -> their own, officers -> assigned to them, admins -> all.
    """
    queryset = ServiceRequest.objects.select_related(
        "citizen", "category", "assigned_officer"
    ).annotate(priority_rank=PRIORITY_RANK)

    role = getattr(user, "role", None)
    if role == Role.ADMIN:
        return queryset
    if role == Role.OFFICER:
        return queryset.filter(assigned_officer=user)
    if role == Role.CITIZEN:
        return queryset.filter(citizen=user)
    return queryset.none()
